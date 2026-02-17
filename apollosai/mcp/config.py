"""Per-org MCP config that merges global + user-defined MCP servers.

Includes TTL cache (5 min) for user MCP configs to prevent N+1 queries
on every conversation start. Cache invalidated by MCP CRUD endpoints.
"""

import json
import logging
import time
import uuid

from openhands.core.config.mcp_config import (
    MCPSHTTPServerConfig,
    MCPStdioServerConfig,
    OpenHandsMCPConfig,
)

logger = logging.getLogger(__name__)


class ApollosAIMCPConfig(OpenHandsMCPConfig):
    """Extends default MCP config with per-user MCP servers.

    Uses TTL cache to prevent N+1 queries on every conversation start.
    MCP CRUD endpoints must call invalidate_mcp_cache(user_id) on changes.
    """

    _cache: dict[str, tuple[float, tuple]] = {}
    _cache_ttl: float = 300.0  # 5 minutes
    _cache_max_size: int = 1000

    @classmethod
    def invalidate_mcp_cache(cls, user_id: str) -> None:
        """Invalidate cached MCP config for a user. Call from MCP CRUD endpoints."""
        cls._cache.pop(user_id, None)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear entire cache. Intended for testing only."""
        cls._cache.clear()

    @staticmethod
    async def create_default_mcp_server_config(
        host: str,
        config: 'OpenHandsConfig',  # noqa: F821
        user_id: str | None = None,
    ) -> tuple[MCPSHTTPServerConfig | None, list[MCPStdioServerConfig]]:
        """Create MCP config merging base config with user's custom MCP servers."""
        # Get base config from parent
        shttp, stdio = await OpenHandsMCPConfig.create_default_mcp_server_config(
            host, config, user_id
        )

        if user_id is None:
            return shttp, stdio

        # Check cache first
        cached = ApollosAIMCPConfig._cache.get(user_id)
        if cached is not None:
            ts, result = cached
            if time.monotonic() - ts < ApollosAIMCPConfig._cache_ttl:
                cached_shttp, cached_stdio = result
                return cached_shttp, list(stdio) + list(cached_stdio)
            del ApollosAIMCPConfig._cache[user_id]

        # Load user's custom MCP servers from DB
        user_stdio: list[MCPStdioServerConfig] = []
        try:
            from sqlalchemy import select

            from apollosai.server.lifespan import get_session_maker
            from apollosai.storage.models.user_mcp_server import (
                MCPServerType,
                UserMCPServer,
            )

            session_maker = get_session_maker()
            if session_maker is None:
                return shttp, stdio

            async with session_maker() as session:
                stmt = select(UserMCPServer).where(
                    UserMCPServer.user_id == uuid.UUID(user_id),
                    UserMCPServer.enabled.is_(True),
                    UserMCPServer.approved.is_(True),
                )
                result = await session.execute(stmt)
                servers = result.scalars().all()

                for srv in servers:
                    if srv.server_type == MCPServerType.STDIO:
                        try:
                            cfg = json.loads(srv.config_encrypted)
                        except (json.JSONDecodeError, TypeError):
                            logger.warning('Invalid config for MCP server %s', srv.id)
                            continue
                        user_stdio.append(
                            MCPStdioServerConfig(
                                name=srv.name,
                                command=cfg.get('command', ''),
                                args=cfg.get('args', []),
                                env=cfg.get('env', {}),
                            )
                        )
        except Exception:
            logger.exception('Failed to load user MCP servers')

        # Cache the user-specific result
        if len(ApollosAIMCPConfig._cache) >= ApollosAIMCPConfig._cache_max_size:
            oldest_key = min(
                ApollosAIMCPConfig._cache,
                key=lambda k: ApollosAIMCPConfig._cache[k][0],
            )
            del ApollosAIMCPConfig._cache[oldest_key]
        ApollosAIMCPConfig._cache[user_id] = (time.monotonic(), (shttp, user_stdio))

        return shttp, list(stdio) + user_stdio
