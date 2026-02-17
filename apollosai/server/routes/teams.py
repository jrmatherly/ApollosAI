"""Team CRUD routes with RBAC.

Review fixes incorporated:
- [M1]: Input validation on team names (Pydantic pattern)

Note: Routes where org_id is not in the path use require_auth + manual
role check via _check_org_role() helper. Routes with org_id in the path
use require_role() dependency directly.
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
    AddTeamMemberRequest,
    CreateTeamRequest,
    TeamResponse,
    UpdateTeamRequest,
)
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.role import Role
from apollosai.storage.models.team import Team
from apollosai.storage.models.team_membership import TeamMembership
from apollosai.storage.models.user import User

router = APIRouter()

ROLE_RANKS = {'owner': 0, 'admin': 1, 'manager': 2, 'member': 3}


async def _check_org_role(
    session: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID, min_role: str,
) -> None:
    """Check user has minimum role in org. Raises PermissionDeniedError."""
    min_rank = ROLE_RANKS.get(min_role, 3)
    stmt = (
        select(OrgMembership, Role)
        .join(Role, OrgMembership.role_id == Role.id)
        .where(OrgMembership.org_id == org_id, OrgMembership.user_id == user_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise PermissionDeniedError('Not a member of this organization')
    _, role = row
    if role.rank > min_rank:
        raise PermissionDeniedError(
            f'Requires {min_role} role (rank {min_rank}), '
            f'you have {role.name} (rank {role.rank})'
        )


@router.post('/api/teams')
async def create_team(
    body: CreateTeamRequest,
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new team within an org. Requires admin role."""
    await _check_org_role(session, user.user_id, body.org_id, 'admin')
    team = Team(id=uuid.uuid4(), org_id=body.org_id, name=body.name)
    session.add(team)
    await session.commit()
    return TeamResponse(id=team.id, name=team.name, org_id=team.org_id)


@router.get('/api/orgs/{org_id}/teams')
async def list_teams(
    org_id: uuid.UUID,
    user: AuthedUser = Depends(require_role('member')),
    session: AsyncSession = Depends(get_db_session),
):
    """List teams in an organization."""
    stmt = select(Team).where(Team.org_id == org_id)
    result = await session.execute(stmt)
    teams = result.scalars().all()
    return [TeamResponse(id=t.id, name=t.name, org_id=t.org_id) for t in teams]


@router.patch('/api/teams/{team_id}')
async def update_team(
    team_id: uuid.UUID,
    body: UpdateTeamRequest,
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """Update a team. Requires admin role in the team's org."""
    team = await session.get(Team, team_id)
    if team is None:
        return JSONResponse(status_code=404, content={'error': 'Team not found'})
    await _check_org_role(session, user.user_id, team.org_id, 'admin')
    if body.name is not None:
        team.name = body.name
    await session.commit()
    return TeamResponse(id=team.id, name=team.name, org_id=team.org_id)


@router.delete('/api/teams/{team_id}')
async def delete_team(
    team_id: uuid.UUID,
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a team. Requires admin role in the team's org."""
    team = await session.get(Team, team_id)
    if team is None:
        return JSONResponse(status_code=404, content={'error': 'Team not found'})
    await _check_org_role(session, user.user_id, team.org_id, 'admin')

    # Remove all team memberships first
    stmt = select(TeamMembership).where(TeamMembership.team_id == team_id)
    result = await session.execute(stmt)
    for m in result.scalars().all():
        await session.delete(m)

    # Clear current_team_id for affected users
    user_stmt = select(User).where(User.current_team_id == team_id)
    user_result = await session.execute(user_stmt)
    for u in user_result.scalars().all():
        u.current_team_id = None

    await session.delete(team)
    await session.commit()
    return {'status': 'deleted'}


@router.post('/api/teams/{team_id}/members')
async def add_team_member(
    team_id: uuid.UUID,
    body: AddTeamMemberRequest,
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """Add a member to a team. Requires manager role in the org."""
    team = await session.get(Team, team_id)
    if team is None:
        return JSONResponse(status_code=404, content={'error': 'Team not found'})
    await _check_org_role(session, user.user_id, team.org_id, 'manager')

    target_user = await session.get(User, body.user_id)
    if target_user is None:
        return JSONResponse(status_code=404, content={'error': 'User not found'})

    # Check not already a member
    existing = await session.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == body.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return JSONResponse(status_code=409, content={'error': 'User already a team member'})

    # Get role
    role_stmt = select(Role).where(Role.name == body.role)
    role_result = await session.execute(role_stmt)
    role = role_result.scalar_one_or_none()
    if role is None:
        role = Role(name=body.role, rank=ROLE_RANKS.get(body.role, 3))
        session.add(role)
        await session.flush()

    membership = TeamMembership(
        team_id=team_id, user_id=body.user_id, role_id=role.id,
    )
    session.add(membership)
    await session.commit()
    return {'user_id': str(body.user_id), 'role': role.name}


@router.get('/api/teams/{team_id}/members')
async def list_team_members(
    team_id: uuid.UUID,
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """List members of a team."""
    team = await session.get(Team, team_id)
    if team is None:
        return JSONResponse(status_code=404, content={'error': 'Team not found'})
    await _check_org_role(session, user.user_id, team.org_id, 'member')

    stmt = (
        select(TeamMembership, Role, User)
        .join(Role, TeamMembership.role_id == Role.id)
        .join(User, TeamMembership.user_id == User.id)
        .where(TeamMembership.team_id == team_id)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            'user_id': str(m.user_id),
            'email': u.email,
            'role_name': r.name,
            'role_rank': r.rank,
        }
        for m, r, u in rows
    ]
