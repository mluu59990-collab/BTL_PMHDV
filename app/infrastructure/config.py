from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Logistics API"
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://logistics:logistics@localhost:5432/logistics"
    )
    db_check_timeout_seconds: float = Field(default=5, gt=0, le=60)

    @field_validator("database_url")
    @classmethod
    def require_async_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(
            ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        ):
            raise ValueError("DATABASE_URL phải dùng postgresql+asyncpg hoặc sqlite+aiosqlite")
        return value
