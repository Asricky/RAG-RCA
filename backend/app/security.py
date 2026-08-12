import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone

from .config import settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, salt_text, expected_text = encoded.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(expected_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(subject: str, token_type: str = "access", ttl: timedelta | None = None) -> str:
    if ttl is None:
        ttl = timedelta(minutes=settings.jwt_access_minutes) if token_type == "access" else timedelta(days=settings.jwt_refresh_days)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "type": token_type, "iat": int(time.time()), "exp": int((datetime.now(timezone.utc) + ttl).timestamp())}
    first = _b64(json.dumps(header, separators=(",", ":")).encode())
    second = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(settings.jwt_secret.encode(), f"{first}.{second}".encode(), hashlib.sha256).digest()
    return f"{first}.{second}.{_b64(signature)}"


def decode_token(token: str, expected_type: str = "access") -> dict:
    first, second, third = token.split(".")
    expected = hmac.new(settings.jwt_secret.encode(), f"{first}.{second}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _unb64(third)):
        raise ValueError("Invalid token signature")
    payload = json.loads(_unb64(second))
    if payload.get("exp", 0) < time.time() or payload.get("type") != expected_type:
        raise ValueError("Expired or invalid token")
    return payload


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
