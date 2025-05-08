import os
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseModel):
    """Application settings."""
    
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_KEY_TPN: str = os.getenv("OPENAI_API_KEY_TPN", "")
    RUNWAY_API_KEY: str = os.getenv("RUNWAY_API_KEY", "")
    RUNWAY_API_VERSION: str = os.getenv("RUNWAY_API_VERSION", "2024-11-06")
    RUNWAY_API_BASE_URL: str = os.getenv("RUNWAY_API_BASE_URL", "https://api.dev.runwayml.com")
    
    # Model settings
    DEFAULT_MODEL: str = "gpt-4o-mini"
    TEMPERATURE: float = 0.7
    
    # Application settings
    APP_NAME: str = "Video Script Generator"
    VERSION: str = "1.0.0"
    
    class Config:
        case_sensitive = True

# Create settings instance
settings = Settings()
