from fastapi import APIRouter

from app.presentation.api.v1 import auth, exchange_rates, fee_configs, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(exchange_rates.router)
api_router.include_router(fee_configs.router)
