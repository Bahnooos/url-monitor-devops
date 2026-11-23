from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "local"
    database_url: str = "postgresql://monitor:secret@localhost:5432/monitordb"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()