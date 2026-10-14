# GCP Cloud Run: Cognito token check

Verifies AWS Cognito JWTs inside a Cloud Run service (FastAPI). No secrets are
involved: only the pool ID, region and app client ID (all public values).

## Files
- `auth.py`: `get_current_user` dependency. Put `Depends(get_current_user)` on every protected route.
- `main.py`: example service. `/health` is public, `/me` is protected.
- `test_auth.py`: offline tests (valid ID/access token, expired, wrong issuer/client/signature, alg=none, garbage).

## Run tests locally
```
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest httpx
pytest -q
```

## Deploy (GCP project fit3184-504001)
```
gcloud config set project fit3184-504001
gcloud run deploy ecoguard-api \
  --source . \
  --region australia-southeast1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-env-vars COGNITO_REGION=ap-southeast-2,COGNITO_USER_POOL_ID=ap-southeast-2_WI1ngaH1k,COGNITO_APP_CLIENT_ID=5tv0jne3t88vcrc5408vrtnl6s,ALLOWED_ORIGINS=http://localhost:5173
```
`--allow-unauthenticated` only means Cloud Run itself does not require a Google
identity. Access is still enforced by the Cognito check in the code, so every
route except `/health` must use `Depends(get_current_user)`.
`--min-instances 0` keeps cost at zero when idle.

## Test with a real token
1. Sign up and log in through the Cognito Hosted UI (or the frontend).
2. Get a token from the CLI for a confirmed test user. Needs a client that allows
   `ALLOW_USER_PASSWORD_AUTH`; otherwise copy the `id_token` from the browser after login:
```
curl https://<service-url>/health                      # 200, public
curl https://<service-url>/me                          # 401, no token
curl -H "Authorization: Bearer <ID_TOKEN>" https://<service-url>/me   # 200, your email
```
Expected: 401 without a token or with an expired/tampered one.

## Notes for the report / demo
- RS256 signature verified against the pool's JWKS (keys cached in memory).
- Checks `iss`, `exp`, `token_use` and the app client ID (`aud` for ID tokens, `client_id` for access tokens).
- Only RS256 is accepted, so `alg: none` and HS256 tokens are rejected.
- No credentials in code or the frontend. Config comes from environment variables.
