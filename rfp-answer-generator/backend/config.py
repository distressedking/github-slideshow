"""
Configuration settings for the RFP Answer Generator
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Application Info
    APP_NAME: str = "RFP Answer Generator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RFP_DIR: Path = DATA_DIR / "rfps"
    ANSWERS_DIR: Path = DATA_DIR / "answers"
    EMBEDDINGS_DIR: Path = DATA_DIR / "embeddings"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"

    # Vector Database
    CHROMA_PERSIST_DIR: str = str(DATA_DIR / "chroma_db")
    COLLECTION_NAME: str = "rfp_documents"

    # Embedding Model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # LLM Settings (Optional - for enhanced generation)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    USE_LLM: bool = False
    LLM_PROVIDER: str = "openai"  # "openai" or "anthropic"

    # Search Settings
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.3

    # Text Processing
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()

# Ensure directories exist
for dir_path in [settings.DATA_DIR, settings.RFP_DIR, settings.ANSWERS_DIR,
                 settings.EMBEDDINGS_DIR, settings.UPLOAD_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
