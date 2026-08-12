import asyncio
import csv
import io
import json
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import Analysis, AnalysisEvidence, AuditLog, Conversation, Dataset, EvaluationRun, GroundTruth, Incident, Message, RefreshToken, User, now
from .security import create_token, decode_token, hash_password, token_hash, verify_password
from .services.llm import generate_rca, provider_status
from .services.log_store import log_store
from .services.retrieval import retrieve


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    log_store.load()
    seed_database()
    if settings.app_env != "test":
        import threading
        threading.Thread(target=log_store.ensure_opensearch, daemon=True).start()
    yield


app = FastAPI(title="5G RCA Copilot API", version="1.0.0", docs_url="/docs", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)


class CreateUserBody(LoginBody):
    full_name: str = Field(min_length=2, max_length=255)
    role: Literal["ADMIN", "ANALYST"] = "ANALYST"


class RefreshBody(BaseModel):
    refresh_token: str


class IncidentBody(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=5000)
    incident_timestamp: datetime = Field(default_factory=now)
    severity: Literal["INFO", "WARNING", "MAJOR", "CRITICAL"] = "MAJOR"
    status: Literal["NEW", "INVESTIGATING", "ANALYZED", "RESOLVED"] = "NEW"
    source_type: Literal["MANUAL", "ANOMALY", "FORECAST", "ANOMALY_FORECAST"] = "MANUAL"
    nodes: list[str] = Field(default_factory=list, max_length=50)


class ConversationBody(BaseModel):
    incident_id: str | None = None
    title: str = Field(default="RCA investigation", max_length=255)


class MessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class AnalysisBody(BaseModel):
    conversation_id: str | None = None
    incident_id: str | None = None
    question: str = Field(min_length=1, max_length=2000)
    ui_context: dict[str, Any] = Field(default_factory=dict)
    retrieval_config: dict[str, Any] = Field(default_factory=dict)


class EvaluationBody(BaseModel):
    name: str = Field(default="Hybrid retrieval benchmark", min_length=3, max_length=255)
    dataset_id: str | None = None
    alpha: float = 0.5
    top_k: int = 10
    time_before_minutes: int = 5
    time_after_minutes: int = 5
    embedding_model: str = Field(default_factory=lambda: settings.embedding_model, max_length=255)


LOGIN_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)
LOGIN_LIMIT = 8
LOGIN_WINDOW_SECONDS = 60
DUMMY_PASSWORD_HASH = hash_password("invalid-password-placeholder")


def public_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.full_name, "role": user.role, "is_active": user.is_active}


def incident_json(item: Incident) -> dict:
    return {"id": item.id, "incident_code": item.incident_code, "title": item.title, "description": item.description, "incident_timestamp": item.incident_timestamp.isoformat(), "severity": item.severity, "status": item.status, "source_type": item.source_type, "nodes": item.nodes or [], "updated_at": item.updated_at.isoformat()}


def dataset_json(item: Dataset) -> dict:
    return {"id": item.id, "name": item.name, "description": item.description, "source_type": item.source_type, "original_filename": item.original_filename, "status": item.status, "total_records": item.total_records, "valid_records": item.valid_records, "rejected_records": item.rejected_records, "indexed_records": item.indexed_records, "created_at": item.created_at.isoformat()}


def audit(db: Session, user_id: str | None, action: str, resource: str, resource_id: str | None = None, details: dict | None = None):
    db.add(AuditLog(user_id=user_id, action=action, resource_type=resource, resource_id=resource_id, details=details or {}))


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        user_id = decode_token(authorization[7:])["sub"]
    except Exception:
        raise HTTPException(401, "Invalid or expired access token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User is unavailable")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, "Admin role required")
    return user


def seed_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "admin@5grca.local"))
        if not admin and settings.seed_demo_users:
            admin = User(email="admin@5grca.local", full_name="Lukas Admin", role="ADMIN", password_hash=hash_password("admin123"))
            analyst = User(email="analyst@5grca.local", full_name="NOC Analyst", role="ANALYST", password_hash=hash_password("analyst123"))
            db.add_all([admin, analyst])
            db.flush()
        if admin and not db.scalar(select(Dataset).where(Dataset.source_type == "SYNTHETIC")):
            db.add(Dataset(name="5G Core Synthetic Demo", description="400 safe synthetic AMF, SMF, and UPF logs", source_type="SYNTHETIC", status="INDEXED", total_records=len(log_store.logs), valid_records=len(log_store.logs), indexed_records=len(log_store.logs), uploaded_by=admin.id, indexed_at=now()))
        if admin and db.scalar(select(func.count()).select_from(Incident)) == 0:
            incident_path = settings.data_dir / "sample_incidents.json"
            ground_path = settings.data_dir / "sample_ground_truth.json"
            incident_map: dict[str, str] = {}
            if incident_path.exists():
                for payload in json.loads(incident_path.read_text(encoding="utf-8")):
                    item = Incident(created_by=admin.id, incident_timestamp=datetime.fromisoformat(payload.pop("incident_timestamp").replace("Z", "+00:00")), **payload)
                    db.add(item)
                    db.flush()
                    incident_map[item.incident_code] = item.id
            if ground_path.exists():
                for payload in json.loads(ground_path.read_text(encoding="utf-8")):
                    code = payload.pop("incident_code")
                    if code in incident_map:
                        db.add(GroundTruth(incident_id=incident_map[code], **payload))
        db.commit()


@app.get("/")
def root():
    return {"name": "5G RCA Copilot API", "docs": "/docs", "status": "operational"}


@app.post("/api/auth/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    client_key = request.client.host if request.client else "unknown"
    attempts = LOGIN_ATTEMPTS[client_key]
    cutoff = time.monotonic() - LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    if len(attempts) >= LOGIN_LIMIT:
        raise HTTPException(429, "Terlalu banyak percobaan login. Coba kembali dalam satu menit.", headers={"Retry-After": "60"})
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    password_valid = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not password_valid or not user.is_active:
        attempts.append(time.monotonic())
        raise HTTPException(401, "Email atau password salah")
    attempts.clear()
    access, refresh = create_token(user.id), create_token(user.id, "refresh")
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash(refresh), expires_at=now() + timedelta(days=settings.jwt_refresh_days)))
    user.last_login_at = now()
    audit(db, user.id, "LOGIN", "USER", user.id, {"email": user.email})
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "user": public_user(user)}


@app.post("/api/auth/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    try:
        user_id = decode_token(body.refresh_token, "refresh")["sub"]
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(body.refresh_token), RefreshToken.revoked_at.is_(None)))
    if not stored:
        raise HTTPException(401, "Refresh token revoked")
    return {"access_token": create_token(user_id)}


@app.post("/api/auth/logout")
def logout(body: RefreshBody, db: Session = Depends(get_db)):
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(body.refresh_token)))
    if stored:
        stored.revoked_at = now()
        db.commit()
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


@app.get("/api/users")
def users(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [public_user(item) for item in db.scalars(select(User).order_by(User.created_at)).all()]


@app.post("/api/users")
def create_user(body: CreateUserBody, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    item = User(email=body.email.lower(), full_name=body.full_name, role=body.role, password_hash=hash_password(body.password))
    db.add(item); audit(db, user.id, "CREATE_USER", "USER", item.id); db.commit(); db.refresh(item)
    return public_user(item)


@app.patch("/api/users/{user_id}")
def update_user(user_id: str, payload: dict, db: Session = Depends(get_db), actor: User = Depends(admin_user)):
    item = db.get(User, user_id)
    if not item: raise HTTPException(404, "User not found")
    if "role" in payload and payload["role"] not in {"ADMIN", "ANALYST"}:
        raise HTTPException(422, "Role must be ADMIN or ANALYST")
    for key in ("full_name", "role", "is_active"):
        if key in payload: setattr(item, key, payload[key])
    audit(db, actor.id, "UPDATE_USER", "USER", item.id, payload); db.commit()
    return public_user(item)


@app.delete("/api/users/{user_id}")
def disable_user(user_id: str, db: Session = Depends(get_db), actor: User = Depends(admin_user)):
    item = db.get(User, user_id)
    if not item: raise HTTPException(404, "User not found")
    item.is_active = False; audit(db, actor.id, "DISABLE_USER", "USER", item.id); db.commit()
    return {"ok": True}


@app.get("/api/logs")
def logs(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), node: str | None = Query(None, max_length=255), component: str | None = Query(None, max_length=50), severity: str | None = Query(None, max_length=50), keyword: str | None = Query(None, max_length=500), trace_id: str | None = Query(None, max_length=255), session_id: str | None = Query(None, max_length=255), error_code: str | None = Query(None, max_length=255), time_from: str | None = None, time_to: str | None = None, _: User = Depends(current_user)):
    rows, total = log_store.query(locals(), limit, offset)
    return {"items": rows, "total": total, "summary": log_store.summary(rows if any((node, component, severity, keyword, trace_id, session_id, error_code, time_from, time_to)) else None)}


@app.post("/api/logs/stream-ticket")
def create_logs_stream_ticket(user: User = Depends(current_user)):
    return {"ticket": create_token(user.id, "stream", timedelta(seconds=60)), "expires_in": 60}


@app.get("/api/logs/stream")
async def logs_stream(ticket: str = Query(..., max_length=1024)):
    try: decode_token(ticket, "stream")
    except Exception: raise HTTPException(401, "Invalid token")
    async def events():
        cursor = None
        while True:
            latest = [item for item in log_store.logs[:10] if not cursor or item["@timestamp"] > cursor]
            if latest:
                cursor = latest[0]["@timestamp"]
                yield f"event: logs\ndata: {json.dumps(latest)}\n\n"
            else:
                yield ": keep-alive\n\n"
            await asyncio.sleep(settings.live_poll_seconds)
    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/logs/{log_id}")
def log_detail(log_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = log_store.get(log_id)
    if not item: raise HTTPException(404, "Log not found")
    audit(db, user.id, "VIEW_LOG", "LOG", None, {"log_id": log_id}); db.commit()
    return item


@app.post("/api/logs/search-related")
def related(payload: dict, _: User = Depends(current_user)):
    log_ids = payload.get("log_ids") or []
    selected = [item for item in log_store.logs if item["log_id"] in log_ids]
    if not selected: raise HTTPException(400, "Select at least one log")
    context = {"selected_nodes": list({item["node"] for item in selected}), "selected_log_ids": log_ids}
    return retrieve(log_store.logs, payload.get("question", "related failure events"), context, {"top_k": payload.get("top_k", 10), "alpha": 0.5})


@app.get("/api/incidents")
def incidents(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [incident_json(item) for item in db.scalars(select(Incident).order_by(Incident.incident_timestamp.desc())).all()]


@app.post("/api/incidents")
def create_incident(body: IncidentBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sequence = db.scalar(select(func.count()).select_from(Incident)) + 1
    item = Incident(incident_code=f"INC-{sequence:03d}", created_by=user.id, **body.model_dump())
    db.add(item); db.flush(); audit(db, user.id, "CREATE_INCIDENT", "INCIDENT", item.id); db.commit(); db.refresh(item)
    return incident_json(item)


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    item = db.get(Incident, incident_id)
    if not item: raise HTTPException(404, "Incident not found")
    analyses = db.scalars(select(Analysis).where(Analysis.incident_id == item.id).order_by(Analysis.created_at.desc())).all()
    return {**incident_json(item), "analyses": [{"id": a.id, "question": a.question, "status": a.status, "created_at": a.created_at.isoformat(), "result": a.result_json} for a in analyses]}


@app.patch("/api/incidents/{incident_id}")
def update_incident(incident_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Incident, incident_id)
    if not item: raise HTTPException(404, "Incident not found")
    allowed_values = {
        "severity": {"INFO", "WARNING", "MAJOR", "CRITICAL"},
        "status": {"NEW", "INVESTIGATING", "ANALYZED", "RESOLVED"},
    }
    for key, values in allowed_values.items():
        if key in payload and payload[key] not in values:
            raise HTTPException(422, f"Invalid incident {key}")
    for key in ("title", "description", "severity", "status", "nodes"):
        if key in payload: setattr(item, key, payload[key])
    if item.status == "RESOLVED": item.resolved_at = now()
    audit(db, user.id, "UPDATE_INCIDENT", "INCIDENT", item.id, payload); db.commit()
    return incident_json(item)


@app.get("/api/datasets")
def datasets(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [dataset_json(item) for item in db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()]


def parse_upload(name: str, content: bytes) -> tuple[list[dict], int]:
    if len(content) > 10 * 1024 * 1024: raise HTTPException(413, "File exceeds 10 MB limit")
    try:
        text_content = content.decode("utf-8")
        if name.lower().endswith(".csv"):
            records = list(csv.DictReader(io.StringIO(text_content)))
        elif name.lower().endswith(".jsonl"):
            records = [json.loads(line) for line in text_content.splitlines() if line.strip()]
        elif name.lower().endswith(".json"):
            records = json.loads(text_content)
        else: raise HTTPException(400, "Only CSV, JSON, and JSONL are supported")
    except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as exc:
        raise HTTPException(400, f"Invalid dataset: {exc}")
    if not isinstance(records, list):
        raise HTTPException(400, "Dataset root must be an array or a sequence of rows")
    if len(records) > 50_000:
        raise HTTPException(413, "Dataset exceeds the 50,000 record limit")
    valid, rejected = [], 0
    aliases = {"source_time": "@timestamp", "network_function": "component", "instance": "node", "log_level": "severity", "body": "message"}
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            rejected += 1; continue
        item = {aliases.get(key, key): value for key, value in raw.items()}
        if not all(item.get(key) for key in ("@timestamp", "node", "component", "severity", "message")):
            rejected += 1; continue
        try:
            datetime.fromisoformat(str(item["@timestamp"]).replace("Z", "+00:00"))
        except ValueError:
            rejected += 1; continue
        item["severity"] = str(item["severity"]).upper()
        item["component"] = str(item["component"]).upper()
        if item["severity"] not in {"INFO", "WARNING", "ERROR", "MAJOR", "CRITICAL"}:
            rejected += 1; continue
        if any(len(str(item.get(key, ""))) > limit for key, limit in {"node": 255, "component": 50, "message": 10_000}.items()):
            rejected += 1; continue
        item["log_id"] = item.get("log_id") or f"UPL-{uuid.uuid4().hex[:10].upper()}"
        item.setdefault("trace_id", ""); item.setdefault("session_id", ""); item.setdefault("error_code", "")
        item.setdefault("metadata", {}); item["search_text"] = item.get("search_text") or f"[{item['node']}] [{item['severity']}] [{item['error_code']}] {item['message']}"
        valid.append(item)
    return valid, rejected


@app.post("/api/datasets/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...), name: str | None = Form(default=None, max_length=255), db: Session = Depends(get_db), user: User = Depends(admin_user)):
    content_length = int(request.headers.get("content-length", "0") or 0)
    if content_length > 11 * 1024 * 1024:
        raise HTTPException(413, "Upload exceeds the request size limit")
    content = await file.read(); rows, rejected = parse_upload(file.filename or "upload", content)
    item = Dataset(name=name or file.filename or "Uploaded dataset", source_type="UPLOAD", original_filename=file.filename, status="UPLOADED", total_records=len(rows) + rejected, valid_records=len(rows), rejected_records=rejected, uploaded_by=user.id, description=json.dumps(rows))
    db.add(item); db.flush(); audit(db, user.id, "UPLOAD_DATASET", "DATASET", item.id, {"valid": len(rows), "rejected": rejected}); db.commit(); db.refresh(item)
    return {**dataset_json(item), "preview": rows[:10]}


@app.post("/api/datasets/{dataset_id}/index")
def index_dataset(dataset_id: str, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    item = db.get(Dataset, dataset_id)
    if not item: raise HTTPException(404, "Dataset not found")
    if item.source_type == "UPLOAD" and item.description:
        try: log_store.add_many(json.loads(item.description))
        except json.JSONDecodeError: pass
    item.status = "INDEXED"; item.indexed_records = item.valid_records; item.indexed_at = now(); audit(db, user.id, "INDEX_DATASET", "DATASET", item.id); db.commit()
    return dataset_json(item)


@app.delete("/api/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    item = db.get(Dataset, dataset_id)
    if not item: raise HTTPException(404, "Dataset not found")
    if item.source_type == "SYNTHETIC": raise HTTPException(400, "Demo dataset cannot be deleted")
    audit(db, user.id, "DELETE_DATASET", "DATASET", item.id); db.delete(item); db.commit(); return {"ok": True}


@app.post("/api/conversations")
def create_conversation(body: ConversationBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = Conversation(user_id=user.id, **body.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "title": item.title, "incident_id": item.incident_id}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Conversation, conversation_id)
    if not item or item.user_id != user.id: raise HTTPException(404, "Conversation not found")
    messages = db.scalars(select(Message).where(Message.conversation_id == item.id).order_by(Message.created_at)).all()
    return {"id": item.id, "title": item.title, "incident_id": item.incident_id, "messages": [{"id": m.id, "sender_type": m.sender_type, "content": m.content, "message_type": m.message_type, "created_at": m.created_at.isoformat()} for m in messages]}


@app.post("/api/conversations/{conversation_id}/messages")
def add_message(conversation_id: str, body: MessageBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id: raise HTTPException(404, "Conversation not found")
    item = Message(conversation_id=conversation_id, sender_type="USER", content=body.content); db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "content": item.content}


@app.post("/api/analysis/retrieve")
def retrieve_only(body: AnalysisBody, _: User = Depends(current_user)):
    if len(json.dumps(body.ui_context)) > 64_000:
        raise HTTPException(413, "UI context is too large")
    context = {**body.ui_context, "incident_id": body.incident_id}
    return retrieve(log_store.logs, body.question, context, body.retrieval_config)


@app.post("/api/analysis/run")
def run_analysis(body: AnalysisBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if len(json.dumps(body.ui_context)) > 64_000:
        raise HTTPException(413, "UI context is too large")
    total_started = time.perf_counter()
    conversation = db.get(Conversation, body.conversation_id) if body.conversation_id else None
    if not conversation:
        conversation = Conversation(user_id=user.id, incident_id=body.incident_id, title=body.question[:80]); db.add(conversation); db.flush()
    user_message = Message(conversation_id=conversation.id, sender_type="USER", content=body.question); db.add(user_message); db.flush()
    incident = db.get(Incident, body.incident_id) if body.incident_id else None
    context = {**body.ui_context, "incident_id": body.incident_id}
    if incident: context.setdefault("incident_timestamp", incident.incident_timestamp.isoformat())
    bundle = retrieve(log_store.logs, body.question, context, body.retrieval_config)
    result, llm_ms, provider = generate_rca(body.question, bundle)
    assistant = Message(conversation_id=conversation.id, sender_type="ASSISTANT", message_type="RCA", content=json.dumps(result, ensure_ascii=False)); db.add(assistant); db.flush()
    total_ms = max(1, int((time.perf_counter() - total_started) * 1000))
    analysis = Analysis(incident_id=body.incident_id, conversation_id=conversation.id, user_message_id=user_message.id, assistant_message_id=assistant.id, question=body.question, status=result["status"], time_from=_optional_datetime(context.get("time_from")), time_to=_optional_datetime(context.get("time_to")), alpha=bundle["retrieval_config"]["alpha"], top_k=bundle["retrieval_config"]["top_k"], candidate_count=bundle["candidate_count"], retrieval_latency_ms=bundle["retrieval_latency_ms"], llm_latency_ms=llm_ms, total_latency_ms=total_ms, embedding_model=settings.embedding_model, llm_provider=provider, llm_model=settings.ollama_model, result_json=result, evidence_json=bundle, ui_context=context)
    db.add(analysis); db.flush()
    for item in bundle["evidence_logs"]:
        db.add(AnalysisEvidence(analysis_id=analysis.id, evidence_id=item["evidence_id"], log_id=item["log_id"], rank=item["rank"], bm25_score=item["bm25_score"], semantic_score=item["semantic_score"], final_score=item["final_score"]))
    if incident and incident.status in ("NEW", "INVESTIGATING"): incident.status = "ANALYZED"
    audit(db, user.id, "RUN_ANALYSIS", "ANALYSIS", analysis.id, {"candidate_count": bundle["candidate_count"], "top_k": bundle["retrieval_config"]["top_k"]}); db.commit()
    return {"analysis_id": analysis.id, "conversation_id": conversation.id, "evidence_bundle": bundle, "rca_result": result, "timing": {"retrieval_ms": bundle["retrieval_latency_ms"], "llm_ms": llm_ms, "total_ms": total_ms}, "provider": provider}


def _optional_datetime(value):
    if not value: return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def ensure_analysis_access(db: Session, item: Analysis, user: User) -> None:
    conversation = db.get(Conversation, item.conversation_id) if item.conversation_id else None
    if user.role != "ADMIN" and (not conversation or conversation.user_id != user.id):
        raise HTTPException(403, "Analysis belongs to another user")


@app.get("/api/analysis/{analysis_id}")
def analysis_detail(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Analysis, analysis_id)
    if not item: raise HTTPException(404, "Analysis not found")
    ensure_analysis_access(db, item, user)
    return {"analysis_id": item.id, "question": item.question, "status": item.status, "evidence_bundle": item.evidence_json, "rca_result": item.result_json, "timing": {"retrieval_ms": item.retrieval_latency_ms, "llm_ms": item.llm_latency_ms, "total_ms": item.total_latency_ms}}


@app.post("/api/analysis/{analysis_id}/expand-evidence")
def expand_analysis(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Analysis, analysis_id)
    if not item: raise HTTPException(404, "Analysis not found")
    ensure_analysis_access(db, item, user)
    body = AnalysisBody(conversation_id=item.conversation_id, incident_id=item.incident_id, question=item.question, ui_context=item.ui_context, retrieval_config={"alpha": float(item.alpha), "top_k": 20, "time_before_minutes": 15, "time_after_minutes": 15})
    return run_analysis(body, db, user)


@app.get("/api/analysis/{analysis_id}/events")
async def analysis_events(analysis_id: str, ticket: str = Query(..., max_length=1024)):
    try: decode_token(ticket, "stream")
    except Exception: raise HTTPException(401, "Invalid token")
    async def events():
        for event, data in [("context_loaded", "Context loaded"), ("candidate_filtering", "Candidate logs found"), ("retrieval_started", "Hybrid retrieval started"), ("retrieval_complete", "Top evidence selected"), ("llm_started", "Generating RCA"), ("analysis_complete", analysis_id)]:
            yield f"event: {event}\ndata: {json.dumps({'message': data})}\n\n"; await asyncio.sleep(0.12)
    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/evaluation/run")
def run_evaluation(body: EvaluationBody, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    started = time.perf_counter(); truths = db.scalars(select(GroundTruth)).all(); precision_values=[]; recall_values=[]; hits=[]; reciprocal=[]; latencies=[]
    for truth in truths:
        incident = db.get(Incident, truth.incident_id)
        bundle = retrieve(log_store.logs, truth.root_cause, {"incident_timestamp": incident.incident_timestamp.isoformat(), "selected_nodes": incident.nodes}, body.model_dump())
        retrieved = [item["log_id"] for item in bundle["evidence_logs"]]; relevant = set(truth.evidence_log_ids); matched = [item for item in retrieved if item in relevant]
        precision_values.append(len(matched) / max(1, len(retrieved))); recall_values.append(len(matched) / max(1, len(relevant))); hits.append(float(bool(matched))); reciprocal.append(1 / (retrieved.index(matched[0]) + 1) if matched else 0); latencies.append(bundle["retrieval_latency_ms"])
    average = lambda values: round(sum(values) / max(1, len(values)), 4)
    metrics = {"precision_at_k": average(precision_values), "recall_at_k": average(recall_values), "hit_rate_at_k": average(hits), "mrr": average(reciprocal), "context_precision": average(precision_values), "context_recall": average(recall_values), "retrieval_latency_ms": round(sum(latencies) / max(1, len(latencies)))}
    item = EvaluationRun(name=body.name, dataset_id=body.dataset_id, alpha=body.alpha, top_k=body.top_k, time_before_minutes=body.time_before_minutes, time_after_minutes=body.time_after_minutes, embedding_model=body.embedding_model, status="SUCCESS", metrics=metrics, completed_at=now(), created_by=user.id)
    db.add(item); db.flush(); audit(db, user.id, "RUN_EVALUATION", "EVALUATION", item.id, metrics); db.commit(); db.refresh(item)
    return evaluation_json(item)


def evaluation_json(item: EvaluationRun) -> dict:
    return {"id": item.id, "name": item.name, "alpha": float(item.alpha), "top_k": item.top_k, "time_before_minutes": item.time_before_minutes, "time_after_minutes": item.time_after_minutes, "embedding_model": item.embedding_model, "status": item.status, "metrics": item.metrics, "created_at": item.created_at.isoformat()}


@app.get("/api/evaluation")
def evaluations(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return [evaluation_json(item) for item in db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())).all()]


@app.get("/api/evaluation/{run_id}")
def evaluation_detail(run_id: str, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    item = db.get(EvaluationRun, run_id)
    if not item: raise HTTPException(404, "Evaluation not found")
    return evaluation_json(item)


@app.get("/api/health")
def health():
    database = "Healthy"
    try:
        with engine.connect() as connection: connection.execute(text("SELECT 1"))
    except Exception: database = "Unavailable"
    ollama = provider_status()
    if database != "Healthy" or log_store.opensearch_status != "Healthy" or ollama.startswith("Unavailable"):
        opensearch = log_store.opensearch_status if log_store.opensearch_status == "Healthy" else f"{log_store.opensearch_status} · in-memory fallback active"
        return {"status": "Degraded", "services": {"backend": "Healthy", "database": database, "opensearch": opensearch, "embedding": f"Healthy · {settings.embedding_model}", "ollama": ollama}, "log_count": len(log_store.logs)}
    return {"status": "Healthy" if database == "Healthy" else "Degraded", "services": {"backend": "Healthy", "database": database, "opensearch": log_store.opensearch_status, "embedding": f"Healthy · {settings.embedding_model}", "ollama": ollama}, "log_count": len(log_store.logs)}


@app.get("/api/health/database")
def health_database():
    try:
        with engine.connect() as connection: connection.execute(text("SELECT 1"))
        return {"status": "Healthy"}
    except Exception as exc: return {"status": "Unavailable", "detail": str(exc)}


@app.get("/api/health/opensearch")
def health_opensearch(): return {"status": log_store.opensearch_status, "url": settings.opensearch_url, "index": settings.opensearch_index}


@app.get("/api/health/ollama")
def health_ollama(): return {"status": provider_status(), "model": settings.ollama_model}
