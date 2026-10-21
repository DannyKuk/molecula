"""Clerk session tokens signed with a key made here, so the login is tested without Clerk."""

import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from molecula.api.login import ClerkLogin

FRONTEND = "https://molecula.example.de"
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_pem(key: rsa.RSAPrivateKey = SIGNING_KEY) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


def clerk_login() -> ClerkLogin:
    return ClerkLogin(public_pem(), [FRONTEND])


def session_token(
    user: str = "user_a",
    *,
    azp: str = FRONTEND,
    ttl: int = 60,
    key: rsa.RSAPrivateKey = SIGNING_KEY,
) -> str:
    now = int(time.time())
    claims = {"sub": user, "sid": "sess_1", "azp": azp, "iat": now, "nbf": now, "exp": now + ttl}
    return jwt.encode(claims, key, algorithm="RS256")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
