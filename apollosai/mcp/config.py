"""Per-org MCP config that merges global + user-defined MCP servers.

Includes TTL cache (5 min) for user MCP configs to prevent N+1 queries
on every conversation start. Cache invalidated by MCP CRUD endpoints.
"""

import asyncio
import json
import logging
import uuid

from cachetools import TTLCache

from openhands.core.config.mcp_config import (
    MCPSHTTPServerConfig,
    MCPStdioServerConfig,
    OpenHandsMCPConfig,
)

logger = logging.getLogger(__name__)


class ApollosAIMCPConfig(OpenHandsMCPConfig):
    """Extends default MCP config with per-user MCP servers.

    Uses TTLCache with async lock for safe concurrent access.
    MCP CRUD endpoints must call invalidate_mcp_cache(user_id) on changes.
    """

    _cache: TTLCache = TTLCache(maxsize=1000, ttl=300)
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def invalidate_mcp_cache(cls, user_id: str) -> None:
        """Invalidate cached MCP config for a user. Call from MCP CRUD endpoints."""
        cls._cache.pop(user_id, None)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear entire cache. Intended for testing only."""
        cls._cache.clear()

    @classmethod
    async def create_default_mcp_server_config(
        cls,
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

        # Check cache (fast path, no lock needed for reads on TTLCache)
        cached = cls._cache.get(user_id)
        if cached is not None:
            cached_shttp, cached_stdio = cached
            return cached_shttp, list(stdio) + list(cached_stdio)

        # Slow path: acquire lock and double-check
        async with cls._lock:
            cached = cls._cache.get(user_id)
            if cached is not None:
                cached_shttp, cached_stdio = cached
                return cached_shttp, list(stdio) + list(cached_stdio)

            user_stdio = await cls._load_user_servers(user_id)
            cls._cache[user_id] = (shttp, user_stdio)

        return shttp, list(stdio) + user_stdio

    @classmethod
    async def _load_user_servers(cls, user_id: str) -> list[MCPStdioServerConfig]:
        """Load user's custom MCP servers from DB."""
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
                return user_stdio

            async with session_maker() as session:
                stmt = select(UserMCPServer).where(
                    UserMCPServer.user_id == uuid.UUID(user_id),
                    UserMCPServer.enabled.is_(True),
                    UserMCPServer.approved.is_(True),
                )
                result = await session.execute(stmt)
                servers = result.scalars().all()

                for srv in servers:
                    if srv.server_type == MCPServerType.STDIO.value:
                        try:
                            from apollosai.storage.encrypt_utils import decrypt_value

                            try:
                                decrypted = decrypt_value(srv.config_encrypted)
                            except Exception:
                                # Fallback: may be plaintext from before encryption
                                decrypted = srv.config_encrypted
                            cfg = json.loads(decrypted)
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

        return user_stdio
