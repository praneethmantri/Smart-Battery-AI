from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment or defaults."""
    
    APP_NAME: str = "Smart Battery AI Service"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    
    # Database Configuration (SQLite by default, compatible with PostgreSQL)
    DATABASE_URL: str = "sqlite:///./data/battery_charging.db"
    
    # ML Model Configuration
    ML_MODEL_PATH: str = "ml/artifacts/unplug_predictor.joblib"
    MODEL_DIR: str = "ml/models"
    
    # Battery Health Protection Defaults
    BATTERY_HEALTH_MAX_LIMIT_PCT: float = 80.0
    FALLBACK_BUFFER_MINUTES: int = 30
    
    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def resolved_database_url(self) -> str:
        """Reliably resolves SQLite database file path across varying execution working directories."""
        if self.is_sqlite:
            prefix = "sqlite:///"
            if self.DATABASE_URL.startswith(prefix):
                path_str = self.DATABASE_URL[len(prefix):]
                if path_str.startswith("./"):
                    path_str = path_str[2:]
                p = Path(path_str)
                if not p.is_absolute():
                    project_root = Path(__file__).resolve().parent.parent.parent.parent
                    p = (project_root / path_str).resolve()
                return f"sqlite:///{p.as_posix()}"
        return self.DATABASE_URL

    @property
    def resolved_model_dir(self) -> Path:
        """Reliably resolves the model directory across various execution working directories."""
        p = Path(self.MODEL_DIR)
        if p.is_absolute() and p.exists():
            return p
        if p.exists():
            return p.resolve()
        
        # Resolve relative to repository root based on file location
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        candidate = project_root / self.MODEL_DIR
        if candidate.exists():
            return candidate
        
        # Check parent of current working directory if running inside backend/
        candidate_cwd = Path.cwd().parent / self.MODEL_DIR
        if candidate_cwd.exists():
            return candidate_cwd
            
        return (project_root / "ml" / "models").resolve()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
