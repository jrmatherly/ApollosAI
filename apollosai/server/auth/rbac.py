"""RBAC FastAPI dependencies for role-based access control.

Review fixes incorporated:
- [C2]: Wire session via Depends(get_db_session), NOT default None
- [C4]: Raise NoCredentialsError on missing user_id, never fabricate UUID
- [C5]: Add PermissionDeniedError to exception handlers in app_server.py
"""

import os
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.auth_error import AuthError, NoCredentialsError
from apollosai.server.deps import get_db_session
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.role import Role


class PermissionDeniedError(AuthError):
    """User lacks required role for this operation."""

    pass


# Review fix [C4]: Well-known sentinel UUID for dev mode
DEV_MODE_USER_ID = uuid.UUID('00000000-0000-0000-0000-000000000000')


@dataclass
class AuthedUser:
    """Authenticated user with resolved role context."""

    user_id: uuid.UUID
    email: str | None
    org_id: uuid.UUID | None
    role_name: str | None
    role_rank: int | None


async def require_auth(request: Request) -> AuthedUser:
    """Validate JWT and return AuthedUser. Raises on failure."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = await EntraIDUserAuth.get_instance(request)
    # Review fix [C4]: Never fabricate random UUID. Use sentinel for dev mode.
    if not auth.user_id:
        if os.environ.get('APOLLOSAI_ALLOW_UNAUTHENTICATED', '').lower() in (
            '1',
            'true',
            'yes',
        ):
            return AuthedUser(
                user_id=DEV_MODE_USER_ID,
                email='dev@localhost',
                org_id=None,
                role_name=None,
                role_rank=None,
            )
        raise NoCredentialsError('No user_id in auth context')
    return AuthedUser(
        user_id=uuid.UUID(auth.user_id),
        email=auth.email,
        org_id=None,
        role_name=None,
        role_rank=None,
    )


def require_role(min_role: str):
    """Dependency factory: require minimum role rank for org context."""
    ROLE_RANKS = {'owner': 0, 'admin': 1, 'manager': 2, 'member': 3}

    async def _check(
        org_id: uuid.UUID,
        user: AuthedUser = Depends(require_auth),
        # Review fix [C2]: Wire via Depends(), NOT default None
        session: AsyncSession = Depends(get_db_session),
    ) -> AuthedUser:
        min_rank = ROLE_RANKS.get(min_role, 3)
        stmt = (
            select(OrgMembership, Role)
            .join(Role, OrgMembership.role_id == Role.id)
            .where(
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user.user_id,
            )
        )
        result = await session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise PermissionDeniedError('Not a member of this organization')
        membership, role = row
        if role.rank > min_rank:
            raise PermissionDeniedError(
                f'Requires {min_role} role (rank {min_rank}), '
                f'you have {role.name} (rank {role.rank})'
            )
        user.org_id = org_id
        user.role_name = role.name
        user.role_rank = role.rank
        return user

    return _check
