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
from pwdlib.exceptions import UnknownHashError

from app.core.admin_passwords import (
    ADMIN_PASSWORD_SCHEME, admin_password_needs_update, hash_admin_password,
    verify_admin_password_hash,
)
from app.core.config import get_settings

# Desk/LDAP 비밀번호의 기존 {SSHA} 형식은 유지한다. 관리자는 hash_admin_password를 사용한다.
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
    if not isinstance(hashed_password, str):
        return False
    try:
        if hashed_password.startswith(ADMIN_PASSWORD_SCHEME + "$"):
            return verify_admin_password_hash(password, hashed_password)
        if hashed_password.startswith(SSHA_PREFIX):
            decoded = base64.b64decode(hashed_password[len(SSHA_PREFIX):], validate=True)
            if len(decoded) <= _SHA1_DIGEST_BYTES:
                return False
            digest, salt = decoded[:_SHA1_DIGEST_BYTES], decoded[_SHA1_DIGEST_BYTES:]
            expected = hashlib.sha1(password.encode("utf-8") + salt).digest()
            return hmac.compare_digest(digest, expected)
        # 기존 Argon2id 계정도 로그인 후 관리자 전용 해시로 이전할 수 있다.
        return _legacy_hash.verify(password, hashed_password)
    except (binascii.Error, ValueError, UnknownHashError):
        return False


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
