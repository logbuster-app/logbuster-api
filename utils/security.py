from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from config import settings
from domain.errors.users import AuthConfigurationError, UnauthorizedError
from domain.schemas.users import AccessToken

_hasher = PasswordHasher()
_dummy_hash = _hasher.hash("conta inexistente")
_algorithm = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _dummy_hash, password) and (
            password_hash is not None
        )
    except (VerificationError, InvalidHashError):
        return False


def _signing_key() -> str:
    key = settings.jwt_secret
    if len(key.encode()) < 32:
        raise AuthConfigurationError()
    return key


def create_access_token(user_id: UUID) -> AccessToken:
    key = _signing_key()
    try:
        expires_in = settings.jwt_expires_in
        if expires_in <= 0:
            raise ValueError
        expiry = datetime.now(UTC) + timedelta(seconds=expires_in)
    except (ValueError, OverflowError) as exc:
        raise AuthConfigurationError() from exc
    token = jwt.encode({"sub": str(user_id), "exp": expiry}, key, algorithm=_algorithm)
    return AccessToken(access_token=token, expires_in=expires_in)


def read_access_token(token: str) -> UUID:
    key = _signing_key()
    try:
        claims = jwt.decode(
            token, key, algorithms=[_algorithm], options={"require": ["sub", "exp"]}
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise UnauthorizedError() from exc
