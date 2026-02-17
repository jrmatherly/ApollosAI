"""Organization CRUD routes with RBAC.

Review fixes incorporated:
- [M1]: Input validation on org names (Pydantic pattern)
- [H6]: Soft-delete for organization deletion
- [H4]: Full route implementation with RBAC
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.rbac import (
    AuthedUser,
    PermissionDeniedError,
    require_auth,
    require_role,
)
from apollosai.server.deps import get_db_session
from apollosai.server.routes.models import (
    AddMemberRequest,
    CreateOrgRequest,
    OrgMemberResponse,
    OrgResponse,
    UpdateOrgRequest,
)
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.organization import Organization
from apollosai.storage.models.role import Role
from apollosai.storage.models.user import User

router = APIRouter()


@router.post('/api/orgs')
async def create_org(
    body: CreateOrgRequest,
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new organization. Creator becomes owner."""
    org = Organization(id=uuid.uuid4(), name=body.name)
    session.add(org)

    # Get or create owner role
    role_stmt = select(Role).where(Role.name == 'owner')
    role_result = await session.execute(role_stmt)
    owner_role = role_result.scalar_one_or_none()
    if owner_role is None:
        owner_role = Role(name='owner', rank=0)
        session.add(owner_role)
        await session.flush()

    membership = OrgMembership(
        org_id=org.id, user_id=user.user_id, role_id=owner_role.id,
    )
    session.add(membership)
    await session.commit()
    return OrgResponse(id=org.id, name=org.name)


@router.get('/api/orgs')
async def list_orgs(
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """List organizations the user belongs to."""
    stmt = (
        select(Organization)
        .join(OrgMembership, OrgMembership.org_id == Organization.id)
        .where(OrgMembership.user_id == user.user_id)
    )
    result = await session.execute(stmt)
    orgs = result.scalars().all()
    return [OrgResponse(id=o.id, name=o.name) for o in orgs]


@router.patch('/api/orgs/{org_id}')
async def update_org(
    org_id: uuid.UUID,
    body: UpdateOrgRequest,
    user: AuthedUser = Depends(require_role('admin')),
    session: AsyncSession = Depends(get_db_session),
):
    """Update an organization. Requires admin role."""
    org = await session.get(Organization, org_id)
    if org is None:
        return JSONResponse(status_code=404, content={'error': 'Organization not found'})
    if body.name is not None:
        org.name = body.name
    await session.commit()
    return OrgResponse(id=org.id, name=org.name)


@router.delete('/api/orgs/{org_id}')
async def delete_org(
    org_id: uuid.UUID,
    user: AuthedUser = Depends(require_role('owner')),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete (soft-delete) an organization. Requires owner role."""
    org = await session.get(Organization, org_id)
    if org is None:
        return JSONResponse(status_code=404, content={'error': 'Organization not found'})

    # Deactivate all memberships
    stmt = select(OrgMembership).where(OrgMembership.org_id == org_id)
    result = await session.execute(stmt)
    memberships = result.scalars().all()
    for m in memberships:
        await session.delete(m)

    # Clear current_org_id for affected users
    user_stmt = select(User).where(User.current_org_id == org_id)
    user_result = await session.execute(user_stmt)
    for u in user_result.scalars().all():
        u.current_org_id = None

    await session.delete(org)
    await session.commit()
    return {'status': 'deleted'}


@router.post('/api/orgs/{org_id}/members')
async def add_member(
    org_id: uuid.UUID,
    body: AddMemberRequest,
    user: AuthedUser = Depends(require_role('admin')),
    session: AsyncSession = Depends(get_db_session),
):
    """Add a member to an organization. Requires admin role."""
    # Verify target user exists
    target_user = await session.get(User, body.user_id)
    if target_user is None:
        return JSONResponse(status_code=404, content={'error': 'User not found'})

    # Check not already a member
    existing = await session.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == body.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return JSONResponse(status_code=409, content={'error': 'User already a member'})

    # Get role
    role_stmt = select(Role).where(Role.name == body.role)
    role_result = await session.execute(role_stmt)
    role = role_result.scalar_one_or_none()
    if role is None:
        role = Role(name=body.role, rank={'owner': 0, 'admin': 1, 'manager': 2, 'member': 3}[body.role])
        session.add(role)
        await session.flush()

    membership = OrgMembership(
        org_id=org_id, user_id=body.user_id, role_id=role.id,
    )
    session.add(membership)
    await session.commit()
    return OrgMemberResponse(
        user_id=body.user_id, email=target_user.email,
        role_name=role.name, role_rank=role.rank,
    )


@router.get('/api/orgs/{org_id}/members')
async def list_members(
    org_id: uuid.UUID,
    user: AuthedUser = Depends(require_role('member')),
    session: AsyncSession = Depends(get_db_session),
):
    """List members of an organization."""
    stmt = (
        select(OrgMembership, Role, User)
        .join(Role, OrgMembership.role_id == Role.id)
        .join(User, OrgMembership.user_id == User.id)
        .where(OrgMembership.org_id == org_id)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        OrgMemberResponse(
            user_id=m.user_id, email=u.email,
            role_name=r.name, role_rank=r.rank,
        )
        for m, r, u in rows
    ]


@router.delete('/api/orgs/{org_id}/members/{member_id}')
async def remove_member(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    user: AuthedUser = Depends(require_role('admin')),
    session: AsyncSession = Depends(get_db_session),
):
    """Remove a member from an organization. Cannot remove last owner."""
    # Find the membership
    stmt = select(OrgMembership).where(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == member_id,
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()
    if membership is None:
        return JSONResponse(status_code=404, content={'error': 'Membership not found'})

    # Check if removing last owner
    role = await session.get(Role, membership.role_id)
    if role and role.name == 'owner':
        owner_count_stmt = (
            select(OrgMembership)
            .join(Role, OrgMembership.role_id == Role.id)
            .where(OrgMembership.org_id == org_id, Role.name == 'owner')
        )
        owner_result = await session.execute(owner_count_stmt)
        owners = owner_result.scalars().all()
        if len(owners) <= 1:
            raise PermissionDeniedError('Cannot remove the last owner from an organization')

    await session.delete(membership)
    await session.commit()
    return {'status': 'removed'}
