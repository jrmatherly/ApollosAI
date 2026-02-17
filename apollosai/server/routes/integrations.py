"""Integration routes: webhook receiver and integration config listing."""

import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.integrations.models import SourceType
from apollosai.integrations.registry import get_integration, list_integrations
from apollosai.server.auth.rbac import require_role
from apollosai.server.deps import get_db_session
from apollosai.storage.models.integration_config import IntegrationConfig

logger = logging.getLogger(__name__)

router = APIRouter()
_require_member = require_role('member')


@router.post('/api/webhooks/{integration_type}')
async def receive_webhook(
    request: Request,
    integration_type: str,
):
    """Receive webhook from any integration. No JWT — verified by per-integration signature."""
    try:
        source = SourceType(integration_type)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content={'error': f'Unknown integration: {integration_type}'},
        )
    manager_cls = get_integration(source)
    if manager_cls is None:
        return JSONResponse(
            status_code=404,
            content={'error': f'Integration not registered: {integration_type}'},
        )
    try:
        # TODO(phase3c): load IntegrationConfig from DB to get webhook_secret
        # and pass to manager constructor. Currently managers have no credentials,
        # so signature validation is skipped (returns True with a warning).
        manager = manager_cls()
        return await manager.handle_webhook(request)
    except Exception:
        logger.exception('Webhook processing error for %s', integration_type)
        return JSONResponse(status_code=500, content={'error': 'internal_error'})


@router.get('/api/orgs/{org_id}/integrations')
async def get_integrations(
    org_id: uuid.UUID,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """List all available integrations and their status for the org."""
    registered = list_integrations()
    configs: dict[str, bool] = {}
    if registered:
        stmt = select(IntegrationConfig).where(IntegrationConfig.org_id == org_id)
        result = await session.execute(stmt)
        for config in result.scalars().all():
            configs[config.integration_type] = config.enabled
    return [
        {'type': t.value, 'enabled': configs.get(t.value, False), 'registered': True}
        for t in registered
    ]
