import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.rbac import require_role
from apollosai.server.deps import get_db_session
from apollosai.server.routes.models import AuditLogResponse
from apollosai.storage.models.audit_log import AuditLog

router = APIRouter()
_require_admin = require_role('admin')


@router.get('/api/admin/orgs/{org_id}/audit')
async def list_audit_logs(
    org_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    user=Depends(_require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """List audit log entries for an organization. Requires admin role."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()
    return [
        AuditLogResponse(
            id=log.id,
            actor_id=log.actor_id,
            action=log.action.value,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]
