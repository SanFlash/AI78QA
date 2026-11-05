from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "local-only-change-me"
    database_url: str = "sqlite:///./ai78qa.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    target_allowlist_required: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

settings = Settings()
