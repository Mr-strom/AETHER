"""Application configuration using Pydantic Settings v2."""

from pathlib import Path
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore


class Settings(BaseSettings):
    """System configuration settings loaded from environment or .env file."""

    APP_NAME: str = "AETHER"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Host & Port
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Hardware & Model Budget Requirements
    RAM_BUDGET_MB: int = 14336
    GPU_LAYERS: int = 999
    MODELS_DIR: Path = Path("./models")
    GRANITE_MODEL_FILENAME: str = "granite-4.0-h-tiny-Q4_K_M.gguf"
    QWEN_MODEL_FILENAME: str = "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./aether.db"

    # Ingestion settings
    DATA_DIR: Path = Path("./data")
    CHUNK_SIZE_CHARS: int = 2048   # ~512 tokens at 4 chars/token
    CHUNK_OVERLAP_CHARS: int = 50

    # Embedding settings
    EMBED_MODEL_NAME: str = "BAAI/bge-m3"
    EMBED_DIM: int = 1024
    EMBED_BATCH_SIZE: int = 32

    # FAISS index
    FAISS_INDEX_PATH: Path = Path("./data/index.faiss")

    # CORS settings
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
