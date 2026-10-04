from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Đọc cấu hình từ biến môi trường / file .env"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CMS Nguonhang1688"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Kết nối DB bất đồng bộ (driver asyncmy)
    database_url: str = "mysql+asyncmy://cms:cms@127.0.0.1:3306/cms_nguonhang1688"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # Khóa nội bộ: chỉ nhận HTTP request từ gateway.
    gateway_shared_secret: str = Field(min_length=32, repr=False)

    # JWT
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS: các origin cách nhau bằng dấu phẩy
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
