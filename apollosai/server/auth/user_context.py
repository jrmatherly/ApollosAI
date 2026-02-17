"""V1 UserContext implementation for Entra ID auth.

Bridges EntraIDUserAuth (V0) into the V1 typed DI system. This is the primary
auth path once V0 is removed (April 2026).

Pattern: Same as AuthUserContextInjector (auth_user_context.py:105-119) but
instantiates EntraIDUserAuth directly instead of going through get_user_auth().

EntraIDUserContext is a @dataclass (matching AuthUserContext pattern).
EntraIDUserContextInjector is a Pydantic model (inherits from UserContextInjector
which extends DiscriminatedUnionMixin -> BaseModel).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from fastapi import Request

from openhands.app_server.services.injector import InjectorState
from openhands.app_server.user.specifiy_user_context import USER_CONTEXT_ATTR
from openhands.app_server.user.user_context import UserContext, UserContextInjector
from openhands.app_server.user.user_models import UserInfo
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE, ProviderType
from openhands.sdk.secret import SecretSource, StaticSecret


@dataclass
class EntraIDUserContext(UserContext):
    """V1 UserContext backed by EntraIDUserAuth.

    Follows the same pattern as AuthUserContext (auth_user_context.py:24-99)
    but delegates to EntraIDUserAuth instead of the generic UserAuth.
    """

    user_auth: EntraIDUserAuth  # type: ignore[name-defined]  # noqa: F821
    _user_info: UserInfo | None = field(default=None, init=False, repr=False)

    async def get_user_id(self) -> str | None:
        return await self.user_auth.get_user_id()

    async def get_user_info(self) -> UserInfo:
        """Get user info -- matches AuthUserContext pattern."""
        if self._user_info is not None:
            return self._user_info
        user_id = await self.user_auth.get_user_id()
        settings = await self.user_auth.get_user_settings()
        if settings:
            self._user_info = UserInfo(
                id=user_id,
                **settings.model_dump(context={'expose_secrets': True}),
            )
        else:
            self._user_info = UserInfo(id=user_id)
        return self._user_info

    async def get_authenticated_git_url(
        self, repository: str, is_optional: bool = False
    ) -> str:
        # TODO: Phase 2 -- integrate with provider tokens for git auth
        return repository

    async def get_provider_tokens(self) -> PROVIDER_TOKEN_TYPE | None:
        return await self.user_auth.get_provider_tokens()

    async def get_latest_token(self, provider_type: ProviderType) -> str | None:
        # TODO: Phase 2 -- per-provider token retrieval
        return None

    async def get_secrets(self) -> dict[str, SecretSource]:
        """Get secrets -- uses StaticSecret (not abstract SecretSource)."""
        secrets = await self.user_auth.get_secrets()
        if secrets is None:
            return {}
        results: dict[str, SecretSource] = {}
        if secrets.custom_secrets:
            for name, custom_secret in secrets.custom_secrets.items():
                results[name] = StaticSecret(
                    value=custom_secret.secret,
                    description=custom_secret.description
                    if custom_secret.description
                    else None,
                )
        return results

    async def get_mcp_api_key(self) -> str | None:
        return await self.user_auth.get_mcp_api_key()


class EntraIDUserContextInjector(UserContextInjector):
    """V1 injector that creates EntraIDUserContext from request.

    Follows AuthUserContextInjector pattern (auth_user_context.py:105-119):
    - Caches the context on the InjectorState via USER_CONTEXT_ATTR
    - Creates EntraIDUserAuth from the request on first call
    - Yields the same EntraIDUserContext on subsequent calls
    """

    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[UserContext, None]:
        user_context = getattr(state, USER_CONTEXT_ATTR, None)
        if user_context is None:
            from apollosai.server.auth.auth_error import AuthError
            from apollosai.server.auth.entraid_auth import EntraIDUserAuth

            if request is None:
                raise AuthError('Request required for authentication')
            user_auth = await EntraIDUserAuth.get_instance(request)
            user_context = EntraIDUserContext(user_auth=user_auth)
            setattr(state, USER_CONTEXT_ATTR, user_context)
        yield user_context
