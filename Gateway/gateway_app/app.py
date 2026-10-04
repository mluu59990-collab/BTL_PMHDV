from contextlib import asynccontextmanager

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from gateway_app.config import Settings

# Chỉ chính xác method + path này được gọi khi chưa có access token.
PUBLIC_ROUTES = {('POST', '/auth/login'), ('POST', '/auth/register'), ('POST', '/auth/refresh'), ('POST', '/auth/logout'), ('GET', '/health')}
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate',
               'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade'}


def clean_headers(headers, *, incoming=False):
    blocked = HOP_HEADERS | {
        name.strip().lower()
        for value in headers.get_list('connection') for name in value.split(',')
    }
    if incoming:
        blocked |= {'host', 'content-length', 'x-gateway-key', 'forwarded'}
    return [(name, value) for name, value in headers.multi_items()
            if name.lower() not in blocked
            and not (incoming and name.lower().startswith(('x-user-', 'x-forwarded-')))]


def validate_access_token(request: Request, settings: Settings):
    values = request.headers.getlist('authorization')
    if len(values) != 1:
        raise HTTPException(401, 'Cần Bearer access token', headers={'WWW-Authenticate': 'Bearer'})
    scheme, separator, token = values[0].partition(' ')
    if scheme.lower() != 'bearer' or not separator or not token:
        raise HTTPException(401, 'Cần Bearer access token', headers={'WWW-Authenticate': 'Bearer'})
    try:
        claims = jwt.decode(token, settings.jwt_secret_key,
                            algorithms=[settings.jwt_algorithm],
                            options={'require': ['exp', 'iat', 'sub', 'jti', 'type', 'role']})
        if (claims['type'] != 'access' or not isinstance(claims['sub'], str)
                or not claims['sub'].isdigit() or int(claims['sub']) <= 0
                or claims['role'] not in {'ADMIN', 'SALE', 'WAREHOUSE', 'ACCOUNTANT', 'CUSTOMER'}):
            raise jwt.InvalidTokenError()
    except jwt.PyJWTError:
        raise HTTPException(401, 'Token không hợp lệ hoặc đã hết hạn',
                            headers={'WWW-Authenticate': 'Bearer'}) from None
    return claims


def create_app(settings: Settings, transport=None):
    @asynccontextmanager
    async def lifespan(app):
        # Dùng chung connection pool; đóng khi gateway dừng.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout, connect=5),
            follow_redirects=False, trust_env=False, transport=transport,
        ) as client:
            app.state.client = client
            yield

    app = FastAPI(title='Logistics API Gateway', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False)

    @app.get('/gateway/health')
    async def gateway_health():
        return {'status': 'ok', 'service': 'gateway'}

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
    async def proxy(request: Request, path: str):
        # Những route mới mặc định được bảo vệ.
        if (request.method, request.url.path) not in PUBLIC_ROUTES:
            validate_access_token(request, settings)

        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > settings.max_body_bytes:
                raise HTTPException(413, 'Request vượt giới hạn dung lượng')
            chunks.append(chunk)

        # Giữ nguyên host cố định; path từ client không thể đổi upstream.
        raw_path = request.scope['raw_path']
        query = request.scope['query_string']
        target = httpx.URL(settings.backend_url).copy_with(
            raw_path=raw_path + (b'?' + query if query else b''))
        headers = clean_headers(httpx.Headers(request.headers.raw), incoming=True)
        headers.append(('x-gateway-key', settings.gateway_shared_secret))
        upstream_request = request.app.state.client.build_request(
            request.method, target, headers=headers, content=b''.join(chunks))
        try:
            upstream = await request.app.state.client.send(upstream_request, stream=True)
        except httpx.TimeoutException:
            raise HTTPException(504, 'Backend phản hồi quá thời gian') from None
        except httpx.RequestError:
            raise HTTPException(502, 'Không kết nối được backend') from None

        response = StreamingResponse(upstream.aiter_raw(), status_code=upstream.status_code,
                                     background=BackgroundTask(upstream.aclose))
        response.raw_headers = [(k.encode('latin-1'), v.encode('latin-1'))
                                for k, v in clean_headers(upstream.headers)]
        return response

    return app
