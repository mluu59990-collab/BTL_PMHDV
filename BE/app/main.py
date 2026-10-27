"""Khởi tạo Backend, kiểm tra Gateway và đăng ký các router nghiệp vụ."""

import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.auth import router as auth_router
from app.core.config import get_settings
from app.customers import create_customer_router
from app.fulfillment import create_fulfillment_router
from app.infrastructure.db.session import engine, get_session
from app.orders import create_order_router
from app.payments import create_payment_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()


app = FastAPI(
    title="Logistics Backend", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)


@app.middleware("http")
async def require_gateway(request: Request, call_next):
    keys = request.headers.getlist("x-gateway-key")
    if len(keys) != 1 or not secrets.compare_digest(
        keys[0].encode(), settings.gateway_shared_secret.encode()
    ):
        return JSONResponse(status_code=403, content={"detail": "Chỉ nhận request qua gateway"})
    return await call_next(request)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("CALL sp_health()"))
    return {"status": "ok", "database": "ok"}


app.include_router(auth_router)
# Các router dùng chung dependency xác thực tài khoản.
app.include_router(create_customer_router(current_user))
app.include_router(create_order_router(current_user))
app.include_router(create_fulfillment_router(current_user))
app.include_router(create_payment_router(current_user))
