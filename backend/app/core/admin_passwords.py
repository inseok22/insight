"""Admin password storage using the standard-library PBKDF2-HMAC-SHA256 KDF."""
import base64
import binascii
import hashlib
import hmac
import secrets

ADMIN_PASSWORD_SCHEME = "pbkdf2_sha256"
ADMIN_PASSWORD_ITERATIONS = 600_000
_MAX_VERIFY_ITERATIONS = 10_000_000


def parse_admin_password_hash(value: str) -> tuple[int, str, bytes] | None:
    """Validate the stored format without running a password derivation."""
    if not isinstance(value, str) or len(value) > 255:
        return None
    parts = value.split("$")
    if len(parts) != 4 or parts[0] != ADMIN_PASSWORD_SCHEME:
        return None
    _, rounds, salt, encoded = parts
    if not rounds.isascii() or not rounds.isdecimal() or len(rounds) > 8:
        return None
    iterations = int(rounds)
    if not 1 <= iterations <= _MAX_VERIFY_ITERATIONS:
        return None
    if len(salt) != 32 or any(char not in "0123456789abcdef" for char in salt):
        return None
    try:
        digest = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(digest) != 32:
        return None
    return iterations, salt, digest


def hash_admin_password(password: str) -> str:
    salt = secrets.token_hex(16)
    # Use the salt string itself as UTF-8 bytes, including in the offline installer.
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"),
        ADMIN_PASSWORD_ITERATIONS, dklen=32,
    )
    encoded = base64.b64encode(digest).decode("ascii")
    return f"{ADMIN_PASSWORD_SCHEME}${ADMIN_PASSWORD_ITERATIONS}${salt}${encoded}"


def verify_admin_password_hash(password: str, value: str) -> bool:
    parsed = parse_admin_password_hash(value)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations, dklen=32,
    )
    return hmac.compare_digest(actual, expected)


def admin_password_needs_update(value: str) -> bool:
    parsed = parse_admin_password_hash(value)
    return parsed is None or parsed[0] < ADMIN_PASSWORD_ITERATIONS
