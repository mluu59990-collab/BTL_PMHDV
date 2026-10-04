from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    backend_url: str = 'http://127.0.0.1:8001'
    jwt_secret_key: str = Field(min_length=32, repr=False)
    jwt_algorithm: str = 'HS256'
    gateway_shared_secret: str = Field(min_length=32, repr=False)
    request_timeout: float = Field(default=15, gt=0)
    max_body_bytes: int = Field(default=1048576, gt=0)

    @field_validator('jwt_algorithm')
    @classmethod
    def supported_algorithm(cls, value):
        if value != 'HS256':
            raise ValueError('Gateway hiện hỗ trợ HS256, phải khớp BE')
        return value

    @field_validator('backend_url')
    @classmethod
    def valid_backend(cls, value):
        url = urlsplit(value)
        if (url.scheme not in ('http', 'https') or not url.hostname
                or url.username or url.password or url.query or url.fragment
                or url.path not in ('', '/')):
            raise ValueError('BACKEND_URL phải là HTTP(S) origin, không chứa path hoặc credentials')
        return value.rstrip('/')
