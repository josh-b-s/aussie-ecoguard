"""Offline tests: a throwaway RSA key stands in for Cognito's signing key."""

import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

os.environ["COGNITO_REGION"] = "ap-southeast-2"
os.environ["COGNITO_USER_POOL_ID"] = "ap-southeast-2_TESTPOOL"
os.environ["COGNITO_APP_CLIENT_ID"] = "testclient123"

import auth  # noqa: E402
from main import app  # noqa: E402

ISSUER = "https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_TESTPOOL"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeSigningKey:
    key = KEY.public_key()


class FakeJwkClient:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey()


@pytest.fixture(autouse=True)
def fake_jwks(monkeypatch):
    monkeypatch.setattr(auth, "get_jwk_client", lambda: FakeJwkClient())


client = TestClient(app)


def make_token(key=KEY, **overrides):
    claims = {
        "sub": "user-1",
        "iss": ISSUER,
        "exp": int(time.time()) + 600,
        "token_use": "id",
        "aud": "testclient123",
        "email": "a@b.com",
        "given_name": "Ada",
        "family_name": "Lovelace",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


def call(token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/me", headers=headers)


def test_health_is_public():
    assert client.get("/health").status_code == 200


def test_valid_id_token():
    r = call(make_token())
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"


def test_valid_access_token():
    r = call(make_token(token_use="access", aud=None, client_id="testclient123"))
    assert r.status_code == 200


def test_missing_token():
    assert call().status_code == 401


def test_expired():
    assert call(make_token(exp=int(time.time()) - 10)).status_code == 401


def test_wrong_issuer():
    assert call(make_token(iss="https://evil.example.com/pool")).status_code == 401


def test_wrong_client_id_id_token():
    assert call(make_token(aud="someone-elses-client")).status_code == 401


def test_wrong_client_id_access_token():
    t = make_token(token_use="access", aud=None, client_id="other")
    assert call(t).status_code == 401


def test_wrong_signature():
    assert call(make_token(key=OTHER_KEY)).status_code == 401


def test_unknown_token_use():
    assert call(make_token(token_use="refresh")).status_code == 401


def test_alg_none_rejected():
    unsigned = jwt.encode(
        {"sub": "x", "iss": ISSUER, "exp": int(time.time()) + 600, "token_use": "id", "aud": "testclient123"},
        key=None,
        algorithm="none",
    )
    assert call(unsigned).status_code == 401


def test_garbage_token():
    assert call("not.a.jwt").status_code == 401
