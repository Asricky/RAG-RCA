import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./rca_copilot.db")
    jwt_secret: str = os.getenv("JWT_SECRET") or "local-demo-secret-change-me"
    jwt_access_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
    jwt_refresh_days: int = int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_user: str = os.getenv("OPENSEARCH_USER", "")
    opensearch_password: str = os.getenv("OPENSEARCH_PASSWORD", "")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "5g-logs-st-v1")
    opensearch_knowledge_index: str = os.getenv("OPENSEARCH_KNOWLEDGE_INDEX", "5g-knowledge-v1")
    opensearch_timeout_seconds: int = int(os.getenv("OPENSEARCH_TIMEOUT_SECONDS", "30"))
    opensearch_startup_retries: int = int(os.getenv("OPENSEARCH_STARTUP_RETRIES", "30"))
    opensearch_startup_retry_seconds: int = int(os.getenv("OPENSEARCH_STARTUP_RETRY_SECONDS", "10"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    index_batch_size: int = int(os.getenv("INDEX_BATCH_SIZE", "256"))
    index_max_retries: int = int(os.getenv("INDEX_MAX_RETRIES", "3"))
    index_progress_every_batches: int = int(os.getenv("INDEX_PROGRESS_EVERY_BATCHES", "10"))
    max_concurrent_index_jobs: int = int(os.getenv("MAX_CONCURRENT_INDEX_JOBS", "1"))
    log_memory_limit: int = int(os.getenv("LOG_MEMORY_LIMIT", "100000"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(250 * 1024 * 1024)))
    max_dataset_records: int = int(os.getenv("MAX_DATASET_RECORDS", "1000000"))
    default_alpha: float = float(os.getenv("DEFAULT_ALPHA", "0.5"))
    default_top_k: int = int(os.getenv("DEFAULT_TOP_K", "10"))
    knowledge_top_k: int = int(os.getenv("KNOWLEDGE_TOP_K", "3"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    llm_allow_mock_fallback: bool = os.getenv("LLM_ALLOW_MOCK_FALLBACK", "true").lower() in {"1", "true", "yes"}
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
    openai_reasoning_effort: str = os.getenv("OPENAI_REASONING_EFFORT", "medium")
    openai_max_output_tokens: int = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "8000"))
    openai_timeout_seconds: int = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "120"))
    openai_organization: str = os.getenv("OPENAI_ORGANIZATION", "")
    openai_project: str = os.getenv("OPENAI_PROJECT", "")
    live_poll_seconds: int = int(os.getenv("LIVE_LOG_POLL_SECONDS", "2"))
    seed_demo_users: bool = os.getenv("SEED_DEMO_USERS", "true").lower() in {"1", "true", "yes"}
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    data_dir: Path = DATA_ROOT
    domain_config_dir: Path = Path(os.getenv("DOMAIN_CONFIG_DIR", str(PROJECT_ROOT / "config" / "domain")))
    demo_data_dir: Path = Path(os.getenv("DEMO_DATA_DIR", str(DATA_ROOT / "demo")))
    knowledge_demo_file: Path = Path(os.getenv("KNOWLEDGE_DEMO_FILE", str(DATA_ROOT / "demo" / "sample_knowledge.json")))
    kpi_source: str = os.getenv("KPI_SOURCE", "demo").lower()
    kpi_demo_file: Path = Path(os.getenv("KPI_DEMO_FILE", str(DATA_ROOT / "demo" / "sample_kpi.csv")))
    kpi_raw_dir: Path = Path(os.getenv("KPI_RAW_DIR", str(DATA_ROOT / "kpi" / "raw")))
    dataset_storage_dir: Path = Path(os.getenv("DATASET_STORAGE_DIR", str(Path(__file__).resolve().parents[1] / "storage" / "datasets")))

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    def validate(self) -> None:
        if self.app_env == "production" and (self.jwt_secret == "local-demo-secret-change-me" or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET must be random and at least 32 characters in production")
        if self.app_env == "production" and self.seed_demo_users:
            raise RuntimeError("SEED_DEMO_USERS must be false when APP_ENV=production")
        if self.llm_provider not in {"openai", "ollama", "mock"}:
            raise RuntimeError("LLM_PROVIDER must be openai, ollama, or mock")
        if self.kpi_source not in {"demo", "raw"}:
            raise RuntimeError("KPI_SOURCE must be demo or raw")
        if self.openai_reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise RuntimeError("OPENAI_REASONING_EFFORT is invalid")
        if self.ollama_timeout_seconds < 1:
            raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be at least 1")
        if self.index_batch_size < 1 or self.index_batch_size > 5000:
            raise RuntimeError("INDEX_BATCH_SIZE must be between 1 and 5000")
        if self.knowledge_top_k < 1 or self.knowledge_top_k > 20:
            raise RuntimeError("KNOWLEDGE_TOP_K must be between 1 and 20")
        if self.max_concurrent_index_jobs < 1 or self.max_concurrent_index_jobs > 16:
            raise RuntimeError("MAX_CONCURRENT_INDEX_JOBS must be between 1 and 16")
        if self.index_progress_every_batches < 1:
            raise RuntimeError("INDEX_PROGRESS_EVERY_BATCHES must be at least 1")
        if self.max_upload_bytes < 1024 or self.max_dataset_records < 1:
            raise RuntimeError("Upload or indexing limits are invalid")


settings = Settings()
