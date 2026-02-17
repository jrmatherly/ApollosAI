# ApollosAI Environment Variables

Reference for all environment variables used by the ApollosAI enterprise auth layer (`apollosai/` package).

See also: `config.template.toml` for the `[apollosai]` section with inline documentation.

---

## Required (Production)

These must be set for the ApollosAI server to start in production mode. Missing any of these triggers a `ValueError` from `ApollosAIServerConfig.verify_config()`.

| Variable | Description | Example |
|----------|-------------|---------|
| `ENTRA_TENANT_ID` | Microsoft Entra ID (Azure AD) tenant identifier | `a1b2c3d4-e5f6-...` |
| `ENTRA_CLIENT_ID` | OAuth2 application (client) ID registered in Entra ID | `f1e2d3c4-b5a6-...` |
| `ENTRA_CLIENT_SECRET` | OAuth2 client secret for confidential client flow | (secret value) |
| `ENTRA_REDIRECT_URI` | OAuth2 redirect URI registered in the Entra app | `https://app.example.com/auth/callback` |
| `JWT_SECRET` | Secret key for signing JWT session tokens. **Minimum 32 characters.** | (random 64-char string) |
| `DATABASE_URL` | PostgreSQL connection string. `postgres://` is auto-converted to `postgresql+asyncpg://` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `APOLLOSAI_ENCRYPTION_KEY` | Master key for AES-256-GCM field-level encryption (HKDF-derived with DATABASE_URL salt) | (random 64-char hex string) |

## Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSION_SECRET` | Separate secret for Starlette `SessionMiddleware`. If unset, falls back to `JWT_SECRET`. | `JWT_SECRET` value |
| `APOLLOSAI_ALLOW_UNAUTHENTICATED` | Allow unauthenticated access (dev/testing only). Parsed strictly: `.lower() in ('1', 'true', 'yes')`. | `false` |
| `FRONTEND_DIRECTORY` | Path to the built frontend static files for serving | `./frontend/dist` |
| `APOLLOSAI_CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3001` |

## Auto-Set

| Variable | Description | Set By |
|----------|-------------|--------|
| `OPENHANDS_CONFIG_CLS` | Points to `apollosai.server.config.ApollosAIServerConfig`. Set by `apollosai/bootstrap.py` if not already overridden. | `bootstrap.py` |

---

## Patterns and Security Rules

### Getter Functions (Not Module-Level Constants)

All env var access uses getter functions (e.g., `get_entra_tenant_id()`) instead of module-level `os.environ.get()`. This prevents import-time caching that breaks `monkeypatch.setenv` in tests.

```python
# Correct
def get_entra_tenant_id() -> str:
    return os.environ.get('ENTRA_TENANT_ID', '')

# Wrong - value cached at import time
ENTRA_TENANT_ID = os.environ.get('ENTRA_TENANT_ID', '')
```

### JWT Hard-Fail

JWT validation failure is always a hard error. The server never falls through from an invalid token to unauthenticated access. The `APOLLOSAI_ALLOW_UNAUTHENTICATED` flag only applies when **no token is present**, not when a token is present but invalid.

### Minimum Secret Length

`JWT_SECRET` must be at least 32 characters. This is enforced at runtime by `ApollosAIServerConfig.verify_config()`.

### JWT Audience Claim

All JWT tokens include `aud: 'apollosai'` and this is validated on decode.

### Auth Error Hierarchy

```
AuthError
  +-- NoCredentialsError    (no token provided)
  +-- InvalidTokenError     (token present but invalid/expired)
  +-- LicenseError          (valid user, invalid license)
```

---

## Quick Start (Development)

Minimal env vars to run the ApollosAI server in development mode with auth bypass:

```bash
export APOLLOSAI_ALLOW_UNAUTHENTICATED=true
export JWT_SECRET=dev-secret-at-least-32-characters-long
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/apollosai_dev
export APOLLOSAI_ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

For full Entra ID OAuth2 flow, also set: `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `ENTRA_REDIRECT_URI`.

---

## Architecture Reference

- **Config class**: `apollosai/server/config.py` (`ApollosAIServerConfig`)
- **Constants/getters**: `apollosai/server/auth/constants.py`
- **JWT utilities**: `apollosai/server/auth/jwt_utils.py`
- **Auth handler**: `apollosai/server/auth/entraid_auth.py` (`EntraIDUserAuth`)
- **V1 bridge**: `apollosai/server/auth/user_context.py` (`EntraIDUserContextInjector`)
- **Database setup**: `apollosai/storage/database.py`
- **Encryption**: `apollosai/storage/encrypt_utils.py`
- **Alembic config**: `apollosai/alembic.ini` + `apollosai/migrations/`
