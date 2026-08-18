import base64
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..config import settings
from .embeddings import embedding_encoder


class KnowledgeRepository:
    """Load safe demo guidance and search it in a dedicated OpenSearch index."""

    def __init__(self):
        self._lock = threading.Lock()
        self.documents: list[dict] = []
        self.status = "Unavailable"
        self.last_error = ""

    def load(self, path: Path | None = None) -> None:
        source = path or settings.knowledge_demo_file
        documents = json.loads(source.read_text(encoding="utf-8")) if source.exists() else []
        if not isinstance(documents, list):
            raise RuntimeError("The demo knowledge file must contain a JSON array")
        with self._lock:
            self.documents = documents

    def _request(self, method: str, path: str, payload: Any | None = None, content_type: str = "application/json") -> Any:
        data = None if payload is None else (payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8"))
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = content_type
        if settings.opensearch_user:
            credentials = base64.b64encode(f"{settings.opensearch_user}:{settings.opensearch_password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        request = urllib.request.Request(
            f"{settings.opensearch_url.rstrip('/')}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=settings.opensearch_timeout_seconds) as response:
            body = response.read()
            return json.loads(body) if body else {}

    def _index_mapping(self) -> dict:
        return {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "_meta": {"embedding_model": settings.embedding_model, "embedding_dimension": settings.embedding_dimension},
                "properties": {
                    "document_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "document_type": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "version": {"type": "keyword"},
                    "interfaces": {"type": "keyword"},
                    "components": {"type": "keyword"},
                    "error_codes": {"type": "keyword"},
                    "symptoms": {"type": "text"},
                    "content": {"type": "text"},
                    "investigation_steps": {"type": "text"},
                    "resolution_steps": {"type": "text"},
                    "recommended_action": {"type": "text"},
                    "metadata": {"type": "object"},
                    "embedding_model": {"type": "keyword"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": settings.embedding_dimension,
                        "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene", "parameters": {"ef_construction": 128, "m": 16}},
                    },
                },
            },
        }

    def ensure_opensearch(self) -> None:
        self.status = "Initializing"
        try:
            self._request("GET", "/")
            embedding_encoder.load()
            try:
                self._request("HEAD", f"/{settings.opensearch_knowledge_index}")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                self._request("PUT", f"/{settings.opensearch_knowledge_index}", self._index_mapping())
            self._validate_index()
            self.index_documents(self.documents)
            self.status = "Healthy"
            self.last_error = ""
        except Exception as exc:
            self.status = "Unavailable"
            self.last_error = str(exc)

    def _validate_index(self) -> None:
        mapping = self._request("GET", f"/{settings.opensearch_knowledge_index}/_mapping")
        current = mapping.get(settings.opensearch_knowledge_index, {}).get("mappings", {})
        vector = current.get("properties", {}).get("embedding", {})
        metadata = current.get("_meta", {})
        if vector.get("dimension") != settings.embedding_dimension or metadata.get("embedding_model") != settings.embedding_model:
            raise RuntimeError(
                f"Knowledge index {settings.opensearch_knowledge_index} is incompatible with {settings.embedding_model}. "
                "Use a new OPENSEARCH_KNOWLEDGE_INDEX name or recreate the development index."
            )

    @staticmethod
    def _document_text(item: dict) -> str:
        values = [
            item.get("title", ""), item.get("content", ""), item.get("recommended_action", ""),
            " ".join(item.get("interfaces", [])), " ".join(item.get("components", [])),
            " ".join(item.get("error_codes", [])), " ".join(item.get("symptoms", [])),
            " ".join(item.get("investigation_steps", [])), " ".join(item.get("resolution_steps", [])),
        ]
        return " ".join(str(value) for value in values if value)

    def index_documents(self, documents: list[dict]) -> int:
        if not documents:
            return 0
        vectors = embedding_encoder.encode_documents([self._document_text(item) for item in documents])
        lines: list[str] = []
        for item, vector in zip(documents, vectors):
            lines.append(json.dumps({"index": {"_index": settings.opensearch_knowledge_index, "_id": item["document_id"]}}))
            lines.append(json.dumps({**item, "embedding": vector, "embedding_model": settings.embedding_model}))
        response = self._request("POST", "/_bulk?refresh=true", ("\n".join(lines) + "\n").encode("utf-8"), "application/x-ndjson")
        if response.get("errors"):
            raise RuntimeError("OpenSearch knowledge indexing failed")
        return len(documents)

    def search(self, query: str, *, interfaces: list[str], components: list[str], error_codes: list[str], limit: int | None = None) -> list[dict]:
        if self.status != "Healthy":
            return []
        should = []
        if interfaces:
            should.append({"terms": {"interfaces": interfaces, "boost": 4.0}})
        if components:
            should.append({"terms": {"components": components, "boost": 2.0}})
        if error_codes:
            should.append({"terms": {"error_codes": error_codes, "boost": 6.0}})
        payload = {
            "size": limit or settings.knowledge_top_k,
            "_source": {"excludes": ["embedding"]},
            "query": {"bool": {
                "must": [{"multi_match": {"query": query, "fields": ["title^4", "content^2", "symptoms^3", "recommended_action^2", "investigation_steps", "resolution_steps"]}}],
                "should": should,
            }},
        }
        response = self._request("POST", f"/{settings.opensearch_knowledge_index}/_search", payload)
        results = [{**hit["_source"], "knowledge_score": round(float(hit.get("_score") or 0.0), 4)} for hit in response.get("hits", {}).get("hits", [])]
        requested_errors = set(error_codes)
        exact_error_matches = [item for item in results if requested_errors & set(item.get("error_codes", []))]
        if exact_error_matches:
            return exact_error_matches
        requested_interfaces = set(interfaces)
        return [item for item in results if requested_interfaces & set(item.get("interfaces", []))]


knowledge_repository = KnowledgeRepository()
