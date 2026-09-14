from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.config import Settings
from app.infrastructure.database import Database
from app.presentation.errors import GlobalExceptionMiddleware, register_exception_handlers
from app.presentation.health import router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(
            settings.database_url.get_secret_value(), settings.db_check_timeout_seconds
        )
        app.state.database = database
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(GlobalExceptionMiddleware)
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
