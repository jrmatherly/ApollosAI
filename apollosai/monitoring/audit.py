"""Audit logging service for admin actions."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.storage.models.audit_log import AuditAction, AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    org_id: uuid.UUID,
    action: AuditAction | str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Record an audit log entry."""
    log = AuditLog(
        actor_id=actor_id,
        org_id=org_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(log)
    await session.flush()
    return log
