import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.application.health import check_readiness
from app.infrastructure.database import Database
from app.presentation.dependencies import get_database

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(database: Annotated[Database, Depends(get_database)]) -> dict[str, str]:
    try:
        return await check_readiness(database)
    except Exception as exc:
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
