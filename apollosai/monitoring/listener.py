"""ApollosAI monitoring listener — extends V0 MonitoringListener with structured logging.

MonitoringListener is V0-only (hard removal April 1, 2026).
Architecture: This class is a thin V0 ADAPTER that delegates to structured logging.
When V1 provides a monitoring extension point, swap the adapter layer only.
"""

import logging

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.events.event import Event
from openhands.server.monitoring import MonitoringListener

logger = logging.getLogger(__name__)


class ApollosAIMonitoringListener(MonitoringListener):
    """V0 adapter — emits structured log events for observability."""

    def on_session_event(self, event: Event) -> None:
        from openhands.core.schema.agent import AgentState
        from openhands.events.observation.agent import (
            AgentStateChangedObservation,
        )

        if (
            isinstance(event, AgentStateChangedObservation)
            and event.agent_state == AgentState.ERROR
        ):
            logger.info(
                'agent_error',
                extra={'signal': 'agent_status_error'},
            )

    def on_agent_session_start(self, success: bool, duration: float) -> None:
        logger.info(
            'agent_session_start',
            extra={
                'signal': 'agent_session_start',
                'success': success,
                'duration': duration,
            },
        )

    def on_create_conversation(self) -> None:
        logger.info(
            'create_conversation',
            extra={'signal': 'create_conversation'},
        )

    @classmethod
    def get_instance(cls, config: OpenHandsConfig) -> 'ApollosAIMonitoringListener':
        return cls()
