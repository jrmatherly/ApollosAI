# ApollosAI Enterprise Layer — Phase 1: Foundation

> **Status:** COMPLETED — merged as part of PR #1 (squash-merged to main)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Get ApollosAI running with Entra ID SSO, PostgreSQL-backed org/team/user models, and settings resolution — the minimum viable enterprise layer.

**Architecture:** Separate `apollosai/` directory extending OpenHands via the same dynamic import + class override pattern used by `enterprise/`. Phase 1 targets the V0 `ServerConfig` subclass — the same approach enterprise currently uses — because V0 is still the runtime path for auth, settings, and secrets resolution. V1 `UserContextInjector` is deferred to Phase 1.5 (see Scope Summary). All storage is async SQLAlchemy 2.0 (mapped_column/Mapped style) on PostgreSQL. Auth via MSAL `ConfidentialClientApplication`.

**Tech Stack:** Python 3.12+, FastAPI, MSAL, SQLAlchemy 2.0+ async, Alembic, PostgreSQL, AES-256-GCM encryption

**Reference docs:** `.scratchpad/apollosai_ent_research/` (docs 00-06)

---

## Task 1: Project Scaffold

**Files:**
- Create: `apollosai/__init__.py`
- Create: `apollosai/server/__init__.py`
- Create: `apollosai/server/auth/__init__.py`
- Create: `apollosai/server/routes/__init__.py`
- Create: `apollosai/storage/__init__.py`
- Create: `apollosai/storage/models/__init__.py`
- Create: `apollosai/storage/stores/__init__.py`
- Create: `apollosai/migrations/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p apollosai/{server/{auth,routes},storage/{models,stores},migrations/versions}
```

**Step 2: Create `__init__.py` files**

Create empty `__init__.py` in each directory above.

**Step 3: Register `apollosai` as an installable package**

In `pyproject.toml`, add to the `packages` list:

```toml
packages = [
  { include = "openhands/**/*" },
  { include = "third_party/**/*" },
  { include = "apollosai/**/*" },       # <-- ADD THIS LINE
  { include = "pyproject.toml", to = "openhands" },
  { include = "poetry.lock", to = "openhands" },
]
```

Without this, `import apollosai` works under `poetry run` (project root on sys.path) but fails in production Docker/pip installs.

**Step 4: Add `msal` and `cryptography` dependencies**

```bash
poetry add msal cryptography
```

**Step 5: Commit**

```bash
git add apollosai/ pyproject.toml
git commit -m "chore: scaffold apollosai enterprise directory structure"
```

---

## Task 2: Database Models — Base + Role

**Files:**
- Create: `apollosai/storage/models/base.py`
- Create: `apollosai/storage/models/role.py`
- Create: `tests/unit/apollosai/storage/__init__.py`
- Create: `tests/unit/apollosai/storage/models/__init__.py`
- Create: `tests/unit/apollosai/storage/models/test_role.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/models/test_role.py
from apollosai.storage.models.role import Role


def test_role_tablename():
    assert Role.__tablename__ == 'role'


def test_role_has_required_columns():
    col_names = {c.name for c in Role.__table__.columns}
    assert 'id' in col_names
    assert 'name' in col_names
    assert 'rank' in col_names
    assert 'created_at' in col_names
    assert 'updated_at' in col_names
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/storage/models/test_role.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'apollosai'`

**Step 3: Write minimal implementation**

```python
# apollosai/storage/models/base.py
"""Shared DeclarativeBase and timestamp mixin for all ApollosAI models."""
import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at to any model."""

    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

```python
# apollosai/storage/models/role.py
from sqlalchemy import Identity
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Role(TimestampMixin, Base):
    __tablename__ = 'role'

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    rank: Mapped[int] = mapped_column()
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/storage/models/test_role.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add apollosai/storage/models/base.py apollosai/storage/models/role.py tests/unit/apollosai/
git commit -m "feat(apollosai): add Base, TimestampMixin, and Role model"
```

---

## Task 3: Database Models — Organization, Team, User, Memberships

**Files:**
- Create: `apollosai/storage/models/organization.py`
- Create: `apollosai/storage/models/team.py`
- Create: `apollosai/storage/models/user.py`
- Create: `apollosai/storage/models/org_membership.py`
- Create: `apollosai/storage/models/team_membership.py`
- Create: `tests/unit/apollosai/storage/models/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/models/test_models.py
from apollosai.storage.models.organization import Organization
from apollosai.storage.models.team import Team
from apollosai.storage.models.user import User
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.team_membership import TeamMembership


def test_organization_tablename():
    assert Organization.__tablename__ == 'organization'


def test_organization_has_required_columns():
    col_names = {c.name for c in Organization.__table__.columns}
    assert {'id', 'name', 'default_llm_model', 'default_llm_base_url',
            'default_max_iterations', 'agent', 'mcp_config',
            'created_at', 'updated_at'}.issubset(col_names)


def test_team_tablename():
    assert Team.__tablename__ == 'team'


def test_team_has_org_fk():
    col_names = {c.name for c in Team.__table__.columns}
    assert 'org_id' in col_names


def test_team_has_timestamps():
    col_names = {c.name for c in Team.__table__.columns}
    assert 'created_at' in col_names
    assert 'updated_at' in col_names


def test_user_tablename():
    assert User.__tablename__ == 'user'


def test_user_has_entra_oid():
    col_names = {c.name for c in User.__table__.columns}
    assert 'entra_oid' in col_names


def test_org_membership_composite_pk():
    pk_cols = {c.name for c in OrgMembership.__table__.primary_key.columns}
    assert pk_cols == {'org_id', 'user_id'}


def test_team_membership_composite_pk():
    pk_cols = {c.name for c in TeamMembership.__table__.primary_key.columns}
    assert pk_cols == {'team_id', 'user_id'}
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/storage/models/test_models.py -v
```

**Step 3: Write implementations**

All models use SQLAlchemy 2.0 `mapped_column`/`Mapped` style and inherit `TimestampMixin` from `base.py`.

```python
# apollosai/storage/models/organization.py
import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = 'organization'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True)

    # LLM defaults
    default_llm_model: Mapped[str | None] = mapped_column(default=None)
    default_llm_base_url: Mapped[str | None] = mapped_column(default=None)
    default_max_iterations: Mapped[int | None] = mapped_column(default=None)
    _default_llm_api_key: Mapped[str | None] = mapped_column(String, default=None)

    # Agent/sandbox config
    agent: Mapped[str | None] = mapped_column(default=None)
    sandbox_base_container_image: Mapped[str | None] = mapped_column(default=None)
    sandbox_runtime_container_image: Mapped[str | None] = mapped_column(default=None)
    mcp_config: Mapped[dict | None] = mapped_column(JSON, default=None)

    # Feature flags
    enable_default_condenser: Mapped[bool] = mapped_column(default=True)
    v1_enabled: Mapped[bool | None] = mapped_column(default=None)
```

```python
# apollosai/storage/models/team.py
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = 'team'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    name: Mapped[str] = mapped_column()

    # Team-level LLM overrides
    llm_model: Mapped[str | None] = mapped_column(default=None)
    llm_base_url: Mapped[str | None] = mapped_column(default=None)
    max_iterations: Mapped[int | None] = mapped_column(default=None)
    _llm_api_key: Mapped[str | None] = mapped_column(String, default=None)

    __table_args__ = (UniqueConstraint('org_id', 'name'),)
```

```python
# apollosai/storage/models/user.py
import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = 'user'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entra_oid: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str | None] = mapped_column(default=None)
    display_name: Mapped[str | None] = mapped_column(default=None)
    current_org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('organization.id'), default=None
    )
    current_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('team.id'), default=None
    )
```

```python
# apollosai/storage/models/org_membership.py
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class OrgMembership(TimestampMixin, Base):
    __tablename__ = 'org_membership'

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('organization.id'), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('user.id'), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey('role.id'))
    status: Mapped[str] = mapped_column(String, default='active')
```

```python
# apollosai/storage/models/team_membership.py
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class TeamMembership(TimestampMixin, Base):
    __tablename__ = 'team_membership'

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('team.id'), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('user.id'), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey('role.id'))

    # Per-user LLM overrides
    _llm_api_key: Mapped[str | None] = mapped_column(String, default=None)
    llm_model: Mapped[str | None] = mapped_column(default=None)
    max_iterations: Mapped[int | None] = mapped_column(default=None)
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/storage/models/test_models.py -v
```

**Step 5: Commit**

```bash
git add apollosai/storage/models/ tests/unit/apollosai/
git commit -m "feat(apollosai): add Organization, Team, User, and Membership models"
```

---

## Task 4: Encryption Utilities

**Files:**
- Create: `apollosai/storage/encrypt_utils.py`
- Create: `tests/unit/apollosai/storage/test_encrypt_utils.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/test_encrypt_utils.py
import pytest


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch):
    """Use monkeypatch for test isolation — prevents accidental use of production keys."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'test-key-for-unit-tests-must-be-32chars!')
    # Reset the cached key so each test gets a fresh derivation
    from apollosai.storage.encrypt_utils import reset_key_cache
    reset_key_cache()


def test_encrypt_decrypt_roundtrip():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    original = 'sk-abc123-my-api-key'
    encrypted = encrypt_value(original)
    assert encrypted != original
    decrypted = decrypt_value(encrypted)
    assert decrypted == original


def test_encrypt_different_each_time():
    """AES-GCM with random nonce should produce different ciphertext."""
    from apollosai.storage.encrypt_utils import encrypt_value
    original = 'same-value'
    enc1 = encrypt_value(original)
    enc2 = encrypt_value(original)
    assert enc1 != enc2


def test_decrypt_invalid_raises():
    from apollosai.storage.encrypt_utils import decrypt_value
    with pytest.raises(Exception):
        decrypt_value('not-valid-ciphertext')


def test_encrypt_empty_string():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    encrypted = encrypt_value('')
    assert decrypt_value(encrypted) == ''


def test_encrypt_unicode():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    original = 'unicode: \u2603\u2764\ufe0f \U0001f680'
    encrypted = encrypt_value(original)
    assert decrypt_value(encrypted) == original


def test_encrypt_long_value():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    original = 'x' * 10000
    encrypted = encrypt_value(original)
    assert decrypt_value(encrypted) == original


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv('APOLLOSAI_ENCRYPTION_KEY', raising=False)
    from apollosai.storage.encrypt_utils import reset_key_cache, encrypt_value
    reset_key_cache()
    with pytest.raises(ValueError, match='APOLLOSAI_ENCRYPTION_KEY'):
        encrypt_value('test')
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/storage/test_encrypt_utils.py -v
```

**Step 3: Write implementation**

```python
# apollosai/storage/encrypt_utils.py
"""AES-256-GCM encryption for sensitive fields.

Uses HKDF key derivation from a master secret with deployment-specific salt.
Consistent with Apollos platform encryption patterns.
"""
import base64
import hashlib
import os
import threading

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

_derived_key: bytes | None = None
_key_lock = threading.Lock()


def _get_deployment_salt() -> bytes:
    """Derive a deployment-specific salt from DATABASE_URL or fallback.

    This ensures two deployments with the same master key derive different
    encryption keys, providing defense-in-depth against key reuse.
    """
    salt_source = os.environ.get('DATABASE_URL', 'apollosai-default-deployment')
    return hashlib.sha256(salt_source.encode()).digest()


def _get_key() -> bytes:
    global _derived_key
    with _key_lock:
        if _derived_key is None:
            master_secret = os.environ.get('APOLLOSAI_ENCRYPTION_KEY', '')
            if not master_secret:
                raise ValueError('APOLLOSAI_ENCRYPTION_KEY environment variable is required')
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=_get_deployment_salt(),
                info=b'apollosai-field-encryption',
            )
            _derived_key = hkdf.derive(master_secret.encode())
    return _derived_key


def encrypt_value(value: str, aad: str | None = None) -> str:
    """Encrypt a value with AES-256-GCM.

    Args:
        value: The plaintext to encrypt.
        aad: Additional Authenticated Data (e.g., 'table:column:record_id').
            Binds ciphertext to its storage location, preventing relocation attacks.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    aad_bytes = aad.encode() if aad else None
    ciphertext = aesgcm.encrypt(nonce, value.encode(), aad_bytes)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_value(value: str, aad: str | None = None) -> str:
    """Decrypt a value encrypted with encrypt_value.

    Args:
        value: The base64-encoded ciphertext.
        aad: Must match the AAD used during encryption.
    """
    key = _get_key()
    raw = base64.b64decode(value.encode())
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    aad_bytes = aad.encode() if aad else None
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
    return plaintext.decode()


def reset_key_cache():
    """Reset cached key — only for use in tests via monkeypatch."""
    global _derived_key
    with _key_lock:
        _derived_key = None
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/storage/test_encrypt_utils.py -v
```

**Step 5: Commit**

```bash
git add apollosai/storage/encrypt_utils.py tests/unit/apollosai/storage/test_encrypt_utils.py
git commit -m "feat(apollosai): add AES-256-GCM encryption utilities"
```

---

## Task 5: ApollosAIServerConfig

**Files:**
- Create: `apollosai/server/config.py`
- Create: `tests/unit/apollosai/server/__init__.py`
- Create: `tests/unit/apollosai/server/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/server/test_config.py
from apollosai.server.config import ApollosAIServerConfig
from openhands.server.config.server_config import ServerConfig
from openhands.server.types import AppMode


def test_is_subclass_of_server_config():
    assert issubclass(ApollosAIServerConfig, ServerConfig)


def test_app_mode_is_saas():
    config = ApollosAIServerConfig()
    assert config.app_mode == AppMode.SAAS


def test_settings_store_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.settings_store_class


def test_user_auth_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.user_auth_class


def test_secret_store_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.secret_store_class


def test_conversation_store_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.conversation_store_class


def test_enable_billing_is_false():
    config = ApollosAIServerConfig()
    assert config.enable_billing is False
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/server/test_config.py -v
```

**Step 3: Write implementation**

```python
# apollosai/server/config.py
import os

from openhands.server.config.server_config import ServerConfig
from openhands.server.types import AppMode


class ApollosAIServerConfig(ServerConfig):
    config_cls: str = os.environ.get('OPENHANDS_CONFIG_CLS', '')
    app_mode = AppMode.SAAS
    enable_billing = False
    hide_llm_settings = False
    # Disable V1 routes in Phase 1 — V1 UserContextInjector deferred to Phase 1.5.
    # Without V1 injectors configured, V1 routes would use the default bridge which
    # may not resolve to EntraIDUserAuth correctly.
    enable_v1: bool = False

    settings_store_class: str = (
        'apollosai.storage.stores.settings_store.ApollosAISettingsStore'
    )
    secret_store_class: str = (
        'apollosai.storage.stores.secrets_store.ApollosAISecretsStore'
    )
    conversation_store_class: str = (
        'apollosai.storage.stores.conversation_store.ApollosAIConversationStore'
    )
    user_auth_class: str = (
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth'
    )
    # Phase 1 uses StandaloneConversationManager (default) — single-replica only.
    # Override to ClusteredConversationManager in Phase 2 for multi-replica deployments.
    # conversation_manager_class: str = (
    #     'openhands.server.conversation_manager.standalone_conversation_manager.StandaloneConversationManager'
    # )
    monitoring_listener_class: str = (
        'openhands.server.monitoring.MonitoringListener'
    )

    def verify_config(self):
        pass

    def get_config(self):
        return {
            'APP_MODE': self.app_mode,
            'GITHUB_CLIENT_ID': self.github_client_id,
            'POSTHOG_CLIENT_KEY': '',
            'FEATURE_FLAGS': {
                'ENABLE_BILLING': False,
                'HIDE_LLM_SETTINGS': False,
            },
        }
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/server/test_config.py -v
```

**Step 5: Commit**

```bash
git add apollosai/server/config.py tests/unit/apollosai/server/
git commit -m "feat(apollosai): add ApollosAIServerConfig with V0 overrides"
```

---

## Task 6: EntraIDUserAuth (V0 Bridge)

**Files:**
- Create: `apollosai/server/auth/auth_error.py`
- Create: `apollosai/server/auth/entraid_auth.py`
- Create: `apollosai/server/auth/constants.py`
- Create: `tests/unit/apollosai/server/auth/__init__.py`
- Create: `tests/unit/apollosai/server/auth/test_entraid_auth.py`

**Step 0: Create auth error classes**

`NoCredentialsError` is enterprise-only (`enterprise/server/auth/auth_error.py`) — not in `openhands/`. ApollosAI needs its own clean-room error hierarchy.

```python
# apollosai/server/auth/auth_error.py
"""Authentication error hierarchy for ApollosAI.

Clean-room implementation — enterprise defines similar errors at
enterprise/server/auth/auth_error.py but we cannot import from there
(PolyForm license) and they are not in openhands/ core.
"""


class AuthError(Exception):
    """Base authentication error."""

    pass


class NoCredentialsError(AuthError):
    """No authentication credentials were provided."""

    pass


class ExpiredError(AuthError):
    """Authentication token has expired."""

    pass
```

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/server/auth/test_entraid_auth.py
import pytest

from apollosai.server.auth.entraid_auth import EntraIDUserAuth
from openhands.server.user_auth.user_auth import UserAuth


def test_is_subclass_of_user_auth():
    assert issubclass(EntraIDUserAuth, UserAuth)


@pytest.mark.asyncio
async def test_get_user_id():
    auth = EntraIDUserAuth(user_id='test-oid-123', email='test@example.com')
    result = await auth.get_user_id()
    assert result == 'test-oid-123'


@pytest.mark.asyncio
async def test_get_user_email():
    auth = EntraIDUserAuth(user_id='test-oid-123', email='test@example.com')
    result = await auth.get_user_email()
    assert result == 'test@example.com'


@pytest.mark.asyncio
async def test_get_access_token_none_when_no_token():
    auth = EntraIDUserAuth(user_id='test-oid-123', email=None)
    result = await auth.get_access_token()
    assert result is None


@pytest.mark.asyncio
async def test_get_provider_tokens_none():
    auth = EntraIDUserAuth(user_id='test-oid-123', email=None)
    result = await auth.get_provider_tokens()
    assert result is None


@pytest.mark.asyncio
async def test_get_instance_raises_without_env_guard(monkeypatch):
    """get_instance must raise NoCredentialsError unless APOLLOSAI_ALLOW_UNAUTHENTICATED is set."""
    from unittest.mock import AsyncMock
    from apollosai.server.auth.auth_error import NoCredentialsError

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    request = AsyncMock()
    with pytest.raises(NoCredentialsError):
        await EntraIDUserAuth.get_instance(request)


@pytest.mark.asyncio
async def test_get_instance_allows_with_env_guard(monkeypatch):
    """get_instance returns unauthenticated instance when env guard is set."""
    from unittest.mock import AsyncMock

    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    request = AsyncMock()
    auth = await EntraIDUserAuth.get_instance(request)
    assert isinstance(auth, EntraIDUserAuth)
    assert await auth.get_user_id() is None
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/server/auth/test_entraid_auth.py -v
```

**Step 3: Write implementation**

```python
# apollosai/server/auth/constants.py
"""Auth constants — secrets accessed via getter functions to avoid module-level exposure.

Secrets are NOT stored as module-level constants to prevent accidental leakage
in error reports, logging middleware, or repr() calls on the module namespace.
"""
import os


# Non-secret configuration (safe as module constants)
ENTRA_TENANT_ID = os.environ.get('ENTRA_TENANT_ID', '')
ENTRA_CLIENT_ID = os.environ.get('ENTRA_CLIENT_ID', '')
ENTRA_REDIRECT_URI = os.environ.get('ENTRA_REDIRECT_URI', '')


def get_entra_client_secret() -> str:
    """Get Entra ID client secret from environment at call time."""
    return os.environ.get('ENTRA_CLIENT_SECRET', '')


def get_jwt_secret() -> str:
    """Get JWT signing secret from environment at call time."""
    return os.environ.get('JWT_SECRET', '')
```

```python
# apollosai/server/auth/entraid_auth.py
from dataclasses import dataclass, field

from pydantic import SecretStr
from fastapi import Request

from openhands.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.server.user_auth.user_auth import UserAuth
from openhands.server.settings import Settings
from openhands.storage.secrets.secrets_store import SecretsStore
from openhands.storage.settings.settings_store import SettingsStore
from openhands.storage.data_models.secrets import Secrets


@dataclass
class EntraIDUserAuth(UserAuth):
    """Entra ID auth implementing the V0 UserAuth ABC.

    Uses @dataclass (matching DefaultUserAuth pattern at default_user_auth.py:23).
    The _settings field is required by UserAuth.get_user_settings() which accesses
    self._settings directly (user_auth.py:67).
    """

    user_id: str | None = None
    email: str | None = None
    access_token: SecretStr | None = None
    refresh_token: SecretStr | None = None
    _settings: Settings | None = field(default=None, init=False, repr=False)

    async def get_user_id(self) -> str | None:
        return self.user_id

    async def get_user_email(self) -> str | None:
        return self.email

    async def get_access_token(self) -> SecretStr | None:
        return self.access_token

    async def get_provider_tokens(self) -> PROVIDER_TOKEN_TYPE | None:
        return None

    async def get_user_settings_store(self) -> SettingsStore:
        from apollosai.storage.stores.settings_store import ApollosAISettingsStore
        from openhands.core.config.utils import load_openhands_config

        config = load_openhands_config()
        return await ApollosAISettingsStore.get_instance(config, self.user_id)

    async def get_secrets_store(self) -> SecretsStore:
        from apollosai.storage.stores.secrets_store import ApollosAISecretsStore
        from openhands.core.config.utils import load_openhands_config

        config = load_openhands_config()
        return await ApollosAISecretsStore.get_instance(config, self.user_id)

    async def get_secrets(self) -> Secrets | None:
        store = await self.get_secrets_store()
        return await store.load()

    async def get_mcp_api_key(self) -> str | None:
        return None

    @classmethod
    async def get_instance(cls, request: Request) -> 'EntraIDUserAuth':
        # Phase 1.5 will extract user from signed JWT cookie or Bearer API key.
        # Until then, require explicit opt-in for unauthenticated access to prevent
        # accidental deployment without auth.
        import os
        if not os.environ.get('APOLLOSAI_ALLOW_UNAUTHENTICATED'):
            from apollosai.server.auth.auth_error import NoCredentialsError
            raise NoCredentialsError('Authentication not configured. Set APOLLOSAI_ALLOW_UNAUTHENTICATED=1 for development.')
        return cls()

    @classmethod
    async def get_for_user(cls, user_id: str) -> 'EntraIDUserAuth':
        # TODO: Phase 1.5 — load cached tokens from DB
        return cls(user_id=user_id)
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/server/auth/test_entraid_auth.py -v
```

**Step 5: Commit**

```bash
git add apollosai/server/auth/ tests/unit/apollosai/server/auth/
git commit -m "feat(apollosai): add EntraIDUserAuth implementing V0 UserAuth ABC"
```

---

## Task 7: ApollosAISettingsStore

**Files:**
- Create: `apollosai/storage/stores/settings_store.py`
- Create: `tests/unit/apollosai/storage/stores/__init__.py`
- Create: `tests/unit/apollosai/storage/stores/test_settings_store.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/stores/test_settings_store.py
from apollosai.storage.stores.settings_store import ApollosAISettingsStore
from openhands.storage.settings.settings_store import SettingsStore


def test_is_subclass_of_settings_store():
    assert issubclass(ApollosAISettingsStore, SettingsStore)


def test_has_required_methods():
    assert hasattr(ApollosAISettingsStore, 'load')
    assert hasattr(ApollosAISettingsStore, 'store')
    assert hasattr(ApollosAISettingsStore, 'get_instance')
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/storage/stores/test_settings_store.py -v
```

**Step 3: Write implementation**

```python
# apollosai/storage/stores/settings_store.py
from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.settings import Settings
from openhands.storage.settings.settings_store import SettingsStore


class ApollosAISettingsStore(SettingsStore):
    """PostgreSQL-backed settings with Org -> Team -> User resolution."""

    def __init__(self, config: OpenHandsConfig, user_id: str | None):
        self.config = config
        self.user_id = user_id

    async def load(self) -> Settings | None:
        # TODO: Implement Org -> Team -> User resolution chain
        # Phase 1: Return default settings from config.
        # Note: Settings.from_config() returns None when no LLM API key is configured.
        # Fall back to empty Settings() to prevent downstream None propagation.
        result = Settings.from_config()
        return result if result is not None else Settings()

    async def store(self, settings: Settings) -> None:
        # TODO: Persist settings to appropriate tier (user/team/org)
        pass

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAISettingsStore':
        return cls(config=config, user_id=user_id)
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/storage/stores/test_settings_store.py -v
```

**Step 5: Commit**

```bash
git add apollosai/storage/stores/settings_store.py tests/unit/apollosai/storage/stores/
git commit -m "feat(apollosai): add ApollosAISettingsStore with stub Org->Team->User resolution"
```

---

## Task 8: ApollosAISecretsStore

**Files:**
- Create: `apollosai/storage/stores/secrets_store.py`
- Create: `tests/unit/apollosai/storage/stores/test_secrets_store.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/stores/test_secrets_store.py
from apollosai.storage.stores.secrets_store import ApollosAISecretsStore
from openhands.storage.secrets.secrets_store import SecretsStore


def test_is_subclass_of_secrets_store():
    assert issubclass(ApollosAISecretsStore, SecretsStore)


def test_has_required_methods():
    assert hasattr(ApollosAISecretsStore, 'load')
    assert hasattr(ApollosAISecretsStore, 'store')
    assert hasattr(ApollosAISecretsStore, 'get_instance')
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/storage/stores/test_secrets_store.py -v
```

**Step 3: Write implementation**

```python
# apollosai/storage/stores/secrets_store.py
from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.secrets import Secrets
from openhands.storage.secrets.secrets_store import SecretsStore


class ApollosAISecretsStore(SecretsStore):
    """PostgreSQL-backed encrypted secrets per user/org."""

    def __init__(self, config: OpenHandsConfig, user_id: str | None):
        self.config = config
        self.user_id = user_id

    async def load(self) -> Secrets | None:
        # TODO: Load encrypted secrets from DB for user + current org
        return Secrets()

    async def store(self, secrets: Secrets) -> None:
        # TODO: Encrypt and persist secrets to DB
        pass

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAISecretsStore':
        return cls(config=config, user_id=user_id)
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/storage/stores/test_secrets_store.py -v
```

**Step 5: Commit**

```bash
git add apollosai/storage/stores/secrets_store.py tests/unit/apollosai/storage/stores/test_secrets_store.py
git commit -m "feat(apollosai): add ApollosAISecretsStore with encrypted storage stub"
```

---

## Task 9: ApollosAIConversationStore

**Files:**
- Create: `apollosai/storage/stores/conversation_store.py`
- Create: `tests/unit/apollosai/storage/stores/test_conversation_store.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/stores/test_conversation_store.py
from apollosai.storage.stores.conversation_store import ApollosAIConversationStore
from openhands.storage.conversation.conversation_store import ConversationStore


def test_is_subclass_of_conversation_store():
    assert issubclass(ApollosAIConversationStore, ConversationStore)


def test_has_required_methods():
    assert hasattr(ApollosAIConversationStore, 'save_metadata')
    assert hasattr(ApollosAIConversationStore, 'get_metadata')
    assert hasattr(ApollosAIConversationStore, 'delete_metadata')
    assert hasattr(ApollosAIConversationStore, 'exists')
    assert hasattr(ApollosAIConversationStore, 'search')
    assert hasattr(ApollosAIConversationStore, 'get_instance')
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/storage/stores/test_conversation_store.py -v
```

**Step 3: Write implementation**

```python
# apollosai/storage/stores/conversation_store.py
from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.conversation.conversation_store import ConversationStore
from openhands.storage.data_models.conversation_metadata import ConversationMetadata
from openhands.storage.data_models.conversation_metadata_result_set import (
    ConversationMetadataResultSet,
)


class ApollosAIConversationStore(ConversationStore):
    """PostgreSQL-backed conversation store scoped to user + org."""

    def __init__(self, config: OpenHandsConfig, user_id: str | None):
        self.config = config
        self.user_id = user_id

    async def save_metadata(self, metadata: ConversationMetadata) -> None:
        # TODO: Persist to DB with user_id + org_id ownership
        pass

    async def get_metadata(self, conversation_id: str) -> ConversationMetadata:
        # TODO: Load from DB, validate user has access
        raise FileNotFoundError(f'Conversation {conversation_id} not found')

    async def delete_metadata(self, conversation_id: str) -> None:
        # TODO: Soft delete from DB
        pass

    async def exists(self, conversation_id: str) -> bool:
        # TODO: Check DB
        return False

    async def search(
        self,
        page_id: str | None = None,
        limit: int = 20,
    ) -> ConversationMetadataResultSet:
        # TODO: Query DB filtered by user_id + org_id
        return ConversationMetadataResultSet(results=[], next_page_id=None)

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAIConversationStore':
        return cls(config=config, user_id=user_id)
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/storage/stores/test_conversation_store.py -v
```

**Step 5: Commit**

```bash
git add apollosai/storage/stores/conversation_store.py tests/unit/apollosai/storage/stores/test_conversation_store.py
git commit -m "feat(apollosai): add ApollosAIConversationStore with user+org scoping stub"
```

---

## Task 10: Entrypoint — `apollosai/app_server.py`

**Files:**
- Create: `apollosai/bootstrap.py`
- Create: `apollosai/app_server.py`
- Create: `tests/unit/apollosai/test_app_server.py`

**Step 1: Write the failing test**

The entrypoint module triggers full V0 server initialization (conversation manager,
MCP server, route mounting). To avoid side effects in unit tests, we split the config
bootstrap into a testable function and test that in isolation.

```python
# tests/unit/apollosai/test_app_server.py
import os

from apollosai.bootstrap import ensure_config_cls


def test_sets_config_cls_when_unset(monkeypatch):
    monkeypatch.delenv('OPENHANDS_CONFIG_CLS', raising=False)
    ensure_config_cls()
    assert os.environ['OPENHANDS_CONFIG_CLS'] == 'apollosai.server.config.ApollosAIServerConfig'


def test_preserves_existing_config_cls(monkeypatch):
    monkeypatch.setenv('OPENHANDS_CONFIG_CLS', 'custom.Config')
    ensure_config_cls()
    assert os.environ['OPENHANDS_CONFIG_CLS'] == 'custom.Config'
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/apollosai/test_app_server.py -v
```

**Step 3: Write implementation**

First, the testable bootstrap module (no heavy imports):

```python
# apollosai/bootstrap.py
"""Config bootstrap — separated from app_server.py for testability."""
import os

APOLLOSAI_CONFIG_CLS = 'apollosai.server.config.ApollosAIServerConfig'


def ensure_config_cls() -> None:
    """Set OPENHANDS_CONFIG_CLS if not already set."""
    if not os.getenv('OPENHANDS_CONFIG_CLS'):
        os.environ['OPENHANDS_CONFIG_CLS'] = APOLLOSAI_CONFIG_CLS
```

Then the entrypoint that uses it:

```python
# apollosai/app_server.py
"""ApollosAI enterprise entrypoint.

Run with:
    PYTHONPATH=".:$PYTHONPATH" uvicorn apollosai.app_server:app --host 0.0.0.0 --port 3000
"""
import os

from dotenv import load_dotenv

load_dotenv()

from apollosai.bootstrap import ensure_config_cls  # noqa: E402

ensure_config_cls()

# Now safe to import OpenHands — config class will be resolved via get_impl()
import socketio  # noqa: E402
from fastapi import Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from openhands.server.app import app as base_app  # noqa: E402
from openhands.server.listen_socket import sio  # noqa: E402
from openhands.server.middleware import CacheControlMiddleware  # noqa: E402
from openhands.server.static import SPAStaticFiles  # noqa: E402
from apollosai.server.auth.auth_error import NoCredentialsError  # noqa: E402

directory = os.getenv('FRONTEND_DIRECTORY', './frontend/build')

# Health check
@base_app.get('/apollosai')
def is_apollosai():
    return {'apollosai': True}


# Exception handlers — return proper 401 instead of 500 for auth errors
@base_app.exception_handler(NoCredentialsError)
async def no_credentials_handler(request: Request, exc: NoCredentialsError):
    return JSONResponse(status_code=401, content={'error': 'Not authenticated'})


# CORS — required for frontend on different port/domain to reach API
allowed_origins = os.environ.get('APOLLOSAI_CORS_ORIGINS', 'http://localhost:3001').split(',')
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Cache control
base_app.add_middleware(CacheControlMiddleware)

# Static files
if os.path.isdir(directory):
    base_app.mount('/', SPAStaticFiles(directory=directory, html=True), name='dist')

# ASGI app
app = socketio.ASGIApp(sio, other_asgi_app=base_app)
```

> **V1 NOTE:** When `enable_v1` is re-enabled in Phase 1.5, the `_get_default_lifespan()` check in `openhands/app_server/config.py:90-95` looks for `'saas'` in `OPENHANDS_CONFIG_CLS`. Since `ApollosAIServerConfig` does not contain "saas", V1 will attempt to run OpenHands' Alembic migrations. Phase 1.5 must either: (a) set `lifespan: None` on the `AppServerConfig` override, (b) rename the config class to include "saas", or (c) contribute a more robust upstream check.

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/apollosai/test_app_server.py -v
```

**Step 5: Commit**

```bash
git add apollosai/bootstrap.py apollosai/app_server.py tests/unit/apollosai/test_app_server.py
git commit -m "feat(apollosai): add enterprise entrypoint with config class bootstrap"
```

---

## Task 11: Run Full Test Suite

**Step 1: Run all ApollosAI unit tests**

```bash
poetry run pytest tests/unit/apollosai/ -v
```

Expected: All tests pass.

**Step 2: Run pre-commit checks**

```bash
pre-commit run --config ./dev_config/python/.pre-commit-config.yaml --files apollosai/**/*.py
```

Fix any lint/format issues.

**Step 3: Final commit**

```bash
git add -u
git commit -m "fix(apollosai): resolve lint and formatting issues"
```

---

## Phase 1 Scope Summary

| Component | Status After Phase 1 |
|-----------|---------------------|
| `ApollosAIServerConfig` | Complete — bridges V0 to ApollosAI classes |
| `EntraIDUserAuth` | Skeleton — methods wired, `get_instance()` needs MSAL cookie/bearer extraction |
| `ApollosAISettingsStore` | Skeleton — falls back to config defaults, DB resolution in Phase 2 |
| `ApollosAISecretsStore` | Skeleton — returns empty secrets, DB persistence in Phase 2 |
| `ApollosAIConversationStore` | Skeleton — all stubs, DB queries in Phase 2 |
| Database models | Complete — Role, Organization, Team, User, OrgMembership, TeamMembership (all with timestamps) |
| Encryption | Complete — AES-256-GCM with HKDF key derivation |
| Entrypoint | Complete — sets config, mounts health check, middleware |
| Alembic migration | Deferred to Phase 1.5 — requires PostgreSQL connection for testing |
| Auth routes (login/callback/logout) | Deferred to Phase 1.5 — requires MSAL config |
| Auth middleware | Deferred to Phase 1.5 — requires cookie extraction logic |
| `EntraIDUserContextInjector` (V1) | Deferred to Phase 1.5 — see note below |

### V0/V1 Strategy Note

The design doc lists `EntraIDUserContextInjector` (V1 `UserContext` ABC, `AppServerConfig.user` injector slot) as a Phase 1 deliverable. Phase 1 targets V0 extension points instead because:

1. **V0 is still the runtime path** — `ServerConfig` → `UserAuth` → stores is how auth, settings, and secrets currently resolve at request time, even with V1 enabled.
2. **Enterprise does the same** — `SaaSServerConfig` overrides V0 classes; V1 is extended via injector replacement in `AppServerConfig`, not route overrides.
3. **V0 removal is April 2026** — gives us time to ship V1 native after the V0 skeleton proves out.

> **RISK MITIGATION:** With only ~6 weeks until V0 removal, Phase 1.5 MUST be started immediately after Phase 1 completes. At minimum, Phase 1.5 should include a `EntraIDUserContextInjector` skeleton that wraps `EntraIDUserAuth`, similar to how `AuthUserContextInjector` wraps `UserAuth` at `openhands/app_server/user/auth_user_context.py:105-119`. This is low effort and prevents a hard dependency on soon-to-be-removed V0 code. If V0 removal is accelerated upstream, the V1 skeleton can serve as the primary auth path.

Phase 1.5 will implement `EntraIDUserContextInjector` alongside MSAL auth routes, since both require a running PostgreSQL and configured MSAL credentials to test meaningfully. Phase 1.5 will also address the V1 lifespan check (see V1 NOTE in Task 10).

**Next:** Phase 1.5 will wire MSAL auth routes, Alembic migration 001, V1 `UserContextInjector`, and fill in the store implementations with real DB queries. That requires a running PostgreSQL instance.
