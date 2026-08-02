import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Computer Use Agent Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Anthropic API Key & Model
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-6")


    
    # Database Settings (PostgreSQL default with SQLite fallback for lightweight testing)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/computer_use_db"
    )
    
    # Display & VNC Settings
    DISPLAY: str = os.getenv("DISPLAY", ":1")
    VNC_HOST: str = os.getenv("VNC_HOST", "localhost")
    VNC_PORT: int = int(os.getenv("VNC_PORT", "6080"))
    
    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
