import threading
from collections.abc import Sequence

from ..config import settings


class SentenceTransformerEncoder:
    """Lazy, process-wide Sentence Transformer encoder for retrieval."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.RLock()
        self.status = "Not loaded"
        self.last_error = ""

    def load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            self.status = "Loading"
            try:
                from sentence_transformers import SentenceTransformer

                try:
                    model = SentenceTransformer(settings.embedding_model, device=settings.embedding_device, local_files_only=True)
                except Exception:
                    model = SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
                dimension_method = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
                dimension = dimension_method()
                if dimension != settings.embedding_dimension:
                    raise RuntimeError(
                        f"Model {settings.embedding_model} produces {dimension} dimensions; "
                        f"EMBEDDING_DIMENSION is {settings.embedding_dimension}"
                    )
                self._model = model
                self.status = "Healthy"
                self.last_error = ""
                return model
            except Exception as exc:
                self.status = "Unavailable"
                self.last_error = str(exc)
                raise

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self.load()
        with self._lock:
            method = getattr(model, "encode_document", model.encode)
            vectors = method(
                list(texts),
                batch_size=settings.embedding_batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        return vectors.astype("float32").tolist()

    def encode_query(self, text: str) -> list[float]:
        model = self.load()
        with self._lock:
            method = getattr(model, "encode_query", model.encode)
            vector = method(
                text,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        return vector.astype("float32").tolist()


embedding_encoder = SentenceTransformerEncoder()
