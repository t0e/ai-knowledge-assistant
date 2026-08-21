import json
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Knowledge Assistant"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "default_dev_secret_key_please_change_in_production_min_32_chars"

    # Authentication & Cookies
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False  # Set to True in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"  # "lax", "strict", or "none"
    COOKIE_DOMAIN: str | None = None

    # Storage & Uploads (Phase 3)
    STORAGE_LOCAL_DIR: str = os.getenv("STORAGE_LOCAL_DIR", "/app/storage")
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".md", ".markdown"]

    # Text Extraction & Chunking (Phase 4)
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    TOKENIZER_MODEL: str = "cl100k_base"

    # Embeddings & Vector Search (Phase 5)
    EMBEDDING_PROVIDER: str = "openai"  # "openai" or "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_BATCH_SIZE: int = 100
    DEFAULT_TOP_K: int = 5
    MAX_TOP_K: int = 20
    OPENAI_API_KEY: str = ""

    # LLM & RAG Orchestration (Phase 6)
    LLM_PROVIDER: str = "openai"  # "openai" or "mock"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1500
    RAG_SIMILARITY_THRESHOLD: float = 0.20
    RAG_MAX_CONTEXT_CHUNKS: int = 5
    RAG_MAX_HISTORY_MESSAGES: int = 6

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return []

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_db"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/knowledge_db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        if v and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("SYNC_DATABASE_URL", mode="before")
    @classmethod
    def assemble_sync_db_connection(cls, v: str) -> str:
        if v and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    # Redis & Background Queue (Phase 7)
    REDIS_URL: str = "redis://localhost:6379/0"
    PROCESSING_QUEUE: str = "ai_knowledge_document_processing"
    JOB_TIMEOUT: int = 300  # 5 minutes
    JOB_MAX_RETRIES: int = 3
    JOB_RETRY_DELAY: int = 5  # seconds

    # Web Ingestion & SSRF Protection (Phase 8)
    MAX_WEB_CONTENT_SIZE_MB: int = 10
    WEB_FETCH_TIMEOUT_SECONDS: int = 15
    WEB_FETCH_MAX_REDIRECTS: int = 5
    WEB_FETCH_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; AIKnowledgeAssistantBot/1.0; +https://github.com)"
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
