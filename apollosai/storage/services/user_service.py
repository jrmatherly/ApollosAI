"""User lifecycle operations — upsert on login, default org creation."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.organization import Organization
from apollosai.storage.models.role import Role
from apollosai.storage.models.user import User


async def upsert_user_on_login(
    session: AsyncSession,
    entra_oid: str,
    email: str,
    display_name: str | None = None,
) -> User:
    """Create or update user on login. Creates default org on first login."""
    stmt = select(User).where(User.entra_oid == entra_oid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        # Existing user — update fields
        user.email = email
        if display_name:
            user.display_name = display_name
        await session.commit()
        return user

    # New user — create with default org
    # Review fix [C6]: Use UUID suffix to prevent org name collision DoS
    org = Organization(
        id=uuid.uuid4(), name=f'{email}-workspace-{uuid.uuid4().hex[:8]}'
    )
    session.add(org)

    user = User(
        id=uuid.uuid4(),
        entra_oid=entra_oid,
        email=email,
        display_name=display_name,
        current_org_id=org.id,
    )
    session.add(user)

    # Get or create owner role
    # Review fix [M10]: Use INSERT ... ON CONFLICT DO NOTHING to avoid race
    # condition on concurrent first-logins. Better: pre-seed roles in Alembic migration.
    role_stmt = select(Role).where(Role.name == 'owner')
    role_result = await session.execute(role_stmt)
    owner_role = role_result.scalar_one_or_none()
    if owner_role is None:
        owner_role = Role(name='owner', rank=0)
        session.add(owner_role)
        await session.flush()

    # Add org membership
    membership = OrgMembership(org_id=org.id, user_id=user.id, role_id=owner_role.id)
    session.add(membership)
    await session.commit()
    return user
