"""Cognito JWT verification for services running on GCP (Cloud Run).

The frontend signs in with AWS Cognito and sends the resulting token as
`Authorization: Bearer <token>`. This module verifies it WITHOUT any shared
secret: Cognito signs tokens with RS256 and publishes its public keys at the
pool's JWKS URL, so we only need the (non-secret) pool ID, region and app
client ID.

Checks performed:
  - signature (RS256, key looked up by the token's `kid`)
  - `exp` (not expired)
  - `iss` equals the user pool's issuer URL
  - token type: ID token (`aud` == app client ID) or
    access token (`client_id` == app client ID)
"""

import os
from functools import lru_cache

import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

bearer_scheme = HTTPBearer(auto_error=False)


class Settings:
    """Read config from environment variables (set on the Cloud Run service)."""

    def __init__(self) -> None:
        self.region = os.environ["COGNITO_REGION"]
        self.user_pool_id = os.environ["COGNITO_USER_POOL_ID"]
        self.client_id = os.environ["COGNITO_APP_CLIENT_ID"]

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_jwk_client() -> PyJWKClient:
    # PyJWKClient caches the fetched keys, so we do not hit Cognito per request.
    return PyJWKClient(get_settings().jwks_url, cache_keys=True)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str) -> dict:
    """Return the verified claims, or raise HTTPException(401)."""
    settings = get_settings()
    try:
        signing_key = get_jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],  # never accept "none" or HS256
            issuer=settings.issuer,
            # `aud` exists on ID tokens only, so it is checked manually below.
            options={"verify_aud": False, "require": ["exp", "iss", "token_use"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except jwt.PyJWTError:
        # Do not leak why verification failed.
        raise _unauthorized("Invalid token")

    token_use = claims.get("token_use")
    if token_use == "id":
        if claims.get("aud") != settings.client_id:
            raise _unauthorized("Invalid token")
    elif token_use == "access":
        if claims.get("client_id") != settings.client_id:
            raise _unauthorized("Invalid token")
    else:
        raise _unauthorized("Invalid token")

    return claims


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency: use on every route that must be protected."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")
    return verify_token(creds.credentials)
