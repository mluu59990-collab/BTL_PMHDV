import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.domain.exceptions import ConflictError, DomainError, ResourceNotFound

logger = logging.getLogger(__name__)


def problem(
    request: Request,
    status: int,
    detail: str,
    *,
    headers: dict[str, str] | None = None,
    **extensions: object,
) -> JSONResponse:
    title = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Error"
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
            **extensions,
        },
    )


class GlobalExceptionMiddleware:
    """ASGI middleware: xử lý lỗi bất ngờ mà không lộ dữ liệu nội bộ."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track_send)
        except Exception:
            logger.exception("Unhandled request error: %s %s", scope["method"], scope["path"])
            if started:
                # Không thể thay status/body sau khi bắt đầu streaming response.
                raise
            response = problem(Request(scope), 500, "An unexpected error occurred.")
            await response(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail = str(exc.detail) if exc.status_code < 500 else "The service is unavailable."
        return problem(request, exc.status_code, detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Không phản chiếu input/ctx: chúng có thể chứa mật khẩu hoặc object không JSON được.
        errors = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return problem(request, 422, "Request validation failed.", errors=errors)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status = 404 if isinstance(exc, ResourceNotFound) else 409 if isinstance(
            exc, ConflictError
        ) else 400
        return problem(request, status, str(exc))
