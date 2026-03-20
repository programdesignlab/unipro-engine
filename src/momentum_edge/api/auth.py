"""JWT authentication via Neon Auth (Better Auth / EdDSA)."""
import base64
from urllib.parse import urlparse

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from momentum_edge.config import settings

_jwks_cache: dict | None = None


def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        url = f"{settings.neon_auth_base_url}/.well-known/jwks.json"
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _get_signing_key(token: str) -> Ed25519PublicKey:
    jwks = _get_jwks()
    kid = jwt.get_unverified_header(token)["kid"]
    for jwk in jwks["keys"]:
        if jwk["kid"] == kid:
            x = jwk["x"]
            # Pad base64url if needed
            x += "=" * (4 - len(x) % 4)
            return Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(x))
    raise ValueError(f"No matching JWK for kid: {kid}")


security = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    token = credentials.credentials
    try:
        parsed = urlparse(settings.neon_auth_base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        signing_key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            key=signing_key,
            algorithms=["EdDSA"],
            issuer=origin,
            audience=origin,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
