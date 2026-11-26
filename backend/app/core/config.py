from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./lights_on.db"
    secret_key: str = "development-only-change-me"
    access_token_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 5
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
