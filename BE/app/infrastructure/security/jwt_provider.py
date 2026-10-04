import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.application.ports import IssuedToken, TokenPayload, TokenProvider
from app.core.clock import utcnow
from app.domain.enums import TokenType
from app.domain.exceptions import AuthenticationError


class JwtTokenProvider(TokenProvider):
    def __init__(self, *, secret: str, algorithm: str, access_minutes: int, refresh_days: int):
        self._secret = secret
        self._algorithm = algorithm
        self._access_ttl = timedelta(minutes=access_minutes)
        self._refresh_ttl = timedelta(days=refresh_days)

    def create_access_token(self, *, user_id: int, role: str) -> IssuedToken:
        return self._encode(user_id, TokenType.ACCESS, self._access_ttl, {"role": role})

    def create_refresh_token(self, *, user_id: int) -> IssuedToken:
        return self._encode(user_id, TokenType.REFRESH, self._refresh_ttl)

    def decode(self, token: str, *, expected_type: TokenType) -> TokenPayload:
        try:
            data = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["exp", "sub", "jti", "type"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Token đã hết hạn") from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Token không hợp lệ") from exc

        if data["type"] != expected_type.value:
            raise AuthenticationError("Sai loại token")
        try:
            user_id = int(data["sub"])
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("Token không hợp lệ") from exc

        return TokenPayload(
            user_id=user_id,
            type=expected_type,
            jti=data["jti"],
            expires_at=datetime.fromtimestamp(data["exp"], tz=timezone.utc),
            role=data.get("role"),
        )

    def _encode(self, user_id: int, token_type: TokenType, ttl: timedelta, extra: dict | None = None) -> IssuedToken:
        now = utcnow()
        expires_at = now + ttl
        jti = uuid.uuid4().hex
        payload = {
            "sub": str(user_id),  # PyJWT yêu cầu sub là chuỗi
            "type": token_type.value,
            "jti": jti,
            "iat": now,
            "exp": expires_at,
            **(extra or {}),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return IssuedToken(token=token, jti=jti, expires_at=expires_at)
