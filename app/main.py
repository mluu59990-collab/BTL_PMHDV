import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.infrastructure.db.session import check_database, engine
from app.presentation.api.exception_handlers import register_exception_handlers
from app.presentation.api.v1.router import api_router

settings = get_settings()
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail-fast: không kết nối được DB thì báo lỗi ngay lúc khởi động
    try:
        await check_database()
    except Exception:
        logger.error("Không kết nối được database. Kiểm tra DATABASE_URL trong .env và đã chạy các file sql/ chưa.")
        raise
    logger.info("Kết nối database OK")
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Backend/CMS quản trị logistic & mua hộ Trung - Việt (Buổi 1: Auth/RBAC, Tỷ giá, Thang bảng phí)",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["Hệ thống"], summary="Kiểm tra server + database")
    async def health():
        await check_database()
        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
