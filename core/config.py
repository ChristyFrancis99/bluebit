from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # App
    APP_NAME: str = "Academic Integrity System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://integrity:integrity@localhost:5432/academic_integrity"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "submissions"
    S3_REGION: str = "us-east-1"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # ML Models
    AI_DETECTION_MODEL_PATH: str = "./weights/ai_detector_v2"
    AI_DETECTION_USE_GPU: bool = False
    AI_DETECTION_MOCK: bool = True  # Use mock until real model weights available

    # Module Weights (defaults)
    DEFAULT_WEIGHT_AI_DETECTION: float = 0.35
    DEFAULT_WEIGHT_PLAGIARISM: float = 0.40
    DEFAULT_WEIGHT_WRITING_PROFILE: float = 0.25
    DEFAULT_WEIGHT_PROCTORING: float = 0.00

    # Risk Thresholds
    RISK_LOW_THRESHOLD: float = 0.35
    RISK_MEDIUM_THRESHOLD: float = 0.65

    # Performance
    MODULE_TIMEOUT_SECONDS: float = 8.0
    MAX_FILE_SIZE_MB: int = 50
    MAX_TEXT_LENGTH: int = 100_000

    # Differential Privacy
    DP_EPSILON: float = 1.0


settings = Settings()
