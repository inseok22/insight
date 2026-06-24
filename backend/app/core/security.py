import base64
import binascii
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from app.core.config import get_settings

# 신규 비밀번호는 LDAP {SSHA}(salted SHA-1) 스킴으로 저장한다.
SSHA_PREFIX = "{SSHA}"
SSHA_SALT_BYTES = 8
_SHA1_DIGEST_BYTES = 20

# 레거시(argon2id) 해시 검증 호환용
_legacy_hash = PasswordHash.recommended()
settings = get_settings()


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(SSHA_SALT_BYTES)
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return SSHA_PREFIX + base64.b64encode(digest + salt).decode("ascii")


def verify_password(password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(SSHA_PREFIX):
        try:
            decoded = base64.b64decode(hashed_password[len(SSHA_PREFIX):])
        except (binascii.Error, ValueError):
            return False
        digest, salt = decoded[:_SHA1_DIGEST_BYTES], decoded[_SHA1_DIGEST_BYTES:]
        expected = hashlib.sha1(password.encode("utf-8") + salt).digest()
        return hmac.compare_digest(digest, expected)
    # {SSHA} 도입 이전에 저장된 argon2id 해시 호환
    return _legacy_hash.verify(password, hashed_password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("토큰이 유효하지 않습니다.") from exc


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="인증에 실패했습니다.",
    headers={"WWW-Authenticate": "Bearer"},
)
