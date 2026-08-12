import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./rca_copilot.db")
    jwt_secret: str = os.getenv("JWT_SECRET") or "local-demo-secret-change-me"
    jwt_access_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
    jwt_refresh_days: int = int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "5g-logs")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "feature-hashing-v1")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    default_alpha: float = float(os.getenv("DEFAULT_ALPHA", "0.5"))
    default_top_k: int = int(os.getenv("DEFAULT_TOP_K", "10"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    live_poll_seconds: int = int(os.getenv("LIVE_LOG_POLL_SECONDS", "2"))
    seed_demo_users: bool = os.getenv("SEED_DEMO_USERS", "true").lower() in {"1", "true", "yes"}
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    def validate(self) -> None:
        if self.app_env == "production" and (self.jwt_secret == "local-demo-secret-change-me" or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET production wajib acak dan minimal 32 karakter")
        if self.app_env == "production" and self.seed_demo_users:
            raise RuntimeError("SEED_DEMO_USERS harus false pada APP_ENV=production")


settings = Settings()
