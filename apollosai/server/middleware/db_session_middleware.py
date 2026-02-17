"""DB-backed server-side session middleware.

Replaces Starlette's cookie-based SessionMiddleware with a thin session_id
cookie pointing to server-side storage in the server_session table.

Review fixes incorporated:
- [H3]: Distinct HKDF info for session encryption (not implemented here —
  session data is stored as JSON in the DB, encrypted at rest by the DB layer)
- [M5]: Probabilistic cleanup of expired sessions and revoked tokens
"""

import logging
import random
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apollosai.storage.models.server_session import ServerSession

logger = logging.getLogger(__name__)

# 1% chance of cleanup per request
CLEANUP_PROBABILITY = 0.01

COOKIE_NAME = 'session_id'


class DBSessionMiddleware:
    """ASGI middleware that stores session data in the server_session table."""

    def __init__(
        self,
        app: ASGIApp,
        session_factory: Callable,
        max_age: int = 86400,
        cookie_name: str = COOKIE_NAME,
        https_only: bool = False,
        same_site: str = 'lax',
    ):
        self.app = app
        self.session_factory = session_factory
        self.max_age = max_age
        self.cookie_name = cookie_name
        self.https_only = https_only
        self.same_site = same_site

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        session_id = connection.cookies.get(self.cookie_name)
        session_data: dict = {}
        is_new_session = False

        # Load existing session from DB
        db_session = self.session_factory()
        if db_session is None:
            # DB not ready (startup) — pass through without session support
            if 'state' not in scope:
                scope['state'] = {}
            scope['state']['session'] = {}
            await self.app(scope, receive, send)
            return

        if session_id:
            row = await db_session.get(ServerSession, session_id)
            if row is not None:
                now = datetime.now(tz=timezone.utc)
                expires_at = row.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at > now:
                    session_data = dict(row.data) if row.data else {}
                else:
                    await db_session.delete(row)
                    await db_session.commit()
                    session_id = None

        if not session_id:
            session_id = secrets.token_urlsafe(32)
            is_new_session = True

        # Attach session data to scope for request.state.session access.
        # Starlette wraps scope['state'] in a State object on first access,
        # so we keep a direct reference to the session dict for the send_wrapper.
        if 'state' not in scope:
            scope['state'] = {}
        scope['state']['session'] = session_data

        # Probabilistic cleanup
        if random.random() < CLEANUP_PROBABILITY:
            await self._cleanup_expired(db_session)

        initial_data = dict(session_data)

        async def send_wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                # Use direct dict reference — scope['state'] may have been
                # wrapped in a Starlette State object by now
                current_data = dict(session_data)
                if is_new_session or current_data != initial_data:
                    await self._save_session(
                        db_session, session_id, current_data,
                    )

                    headers = MutableHeaders(scope=message)
                    cookie_parts = [
                        f'{self.cookie_name}={session_id}',
                        f'Max-Age={self.max_age}',
                        'Path=/',
                        'HttpOnly',
                        f'SameSite={self.same_site}',
                    ]
                    if self.https_only:
                        cookie_parts.append('Secure')
                    headers.append('set-cookie', '; '.join(cookie_parts))

            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _save_session(
        self, db_session: object, session_id: str, data: dict,
    ) -> None:
        """Persist session data to the server_session table."""
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self.max_age)
        existing = await db_session.get(ServerSession, session_id)
        if existing is not None:
            existing.data = data
            existing.expires_at = expires_at
        else:
            row = ServerSession(
                session_id=session_id,
                data=data,
                expires_at=expires_at,
            )
            db_session.add(row)
        await db_session.commit()

    async def _cleanup_expired(self, db_session: object) -> None:
        """Probabilistic cleanup of expired sessions and revoked tokens."""
        from sqlalchemy import delete

        from apollosai.storage.models.revoked_token import RevokedToken

        now = datetime.now(tz=timezone.utc)
        try:
            session_result = await db_session.execute(
                delete(ServerSession).where(ServerSession.expires_at < now)
            )
            token_result = await db_session.execute(
                delete(RevokedToken).where(RevokedToken.expires_at < now)
            )
            await db_session.commit()
            total = (session_result.rowcount or 0) + (token_result.rowcount or 0)
            if total > 0:
                logger.info('Session cleanup: removed %d expired records', total)
        except Exception:
            logger.exception('Session cleanup failed')
