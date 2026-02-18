import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.rbac import require_role
from apollosai.server.deps import get_db_session
from apollosai.server.routes.models import AuditLogResponse, PaginatedAuditLogResponse
from apollosai.storage.models.audit_log import AuditLog

router = APIRouter()
_require_admin = require_role('admin')


@router.get('/api/admin/orgs/{org_id}/audit')
async def list_audit_logs(
    org_id: uuid.UUID,
    limit: int = Query(default=25, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    user=Depends(_require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedAuditLogResponse:
    """List audit log entries for an organization with pagination. Requires admin role."""
    # Build base filter
    base_filter = [AuditLog.org_id == org_id]
    if action:
        base_filter.append(AuditLog.action == action)
    if actor_id:
        base_filter.append(AuditLog.actor_id == actor_id)

    # Count query
    count_stmt = select(func.count()).select_from(AuditLog).where(*base_filter)
    total = (await session.execute(count_stmt)).scalar_one()

    # Data query
    stmt = (
        select(AuditLog)
        .where(*base_filter)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()

    return PaginatedAuditLogResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                actor_id=log.actor_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
