"""MSAL ConfidentialClientApplication wrapper for Entra ID OAuth2.

We use MSAL (not Authlib) because:
1. MSAL handles Azure-specific iss claim validation correctly
2. Built-in token cache with SerializableTokenCache for persistence
3. Proven in Apollos platform
"""

import msal

from apollosai.server.auth.constants import (
    get_entra_client_id,
    get_entra_client_secret,
    get_entra_redirect_uri,
    get_entra_tenant_id,
)

# Scopes for OpenID Connect + profile access
SCOPES = ['User.Read']


def get_msal_app(
    cache: msal.SerializableTokenCache | None = None,
) -> msal.ConfidentialClientApplication:
    """Create a new MSAL ConfidentialClientApplication.

    Args:
        cache: Optional token cache for persistence. Pass a SerializableTokenCache
               loaded from DB for returning users.
    """
    authority = f'https://login.microsoftonline.com/{get_entra_tenant_id()}'
    return msal.ConfidentialClientApplication(
        client_id=get_entra_client_id(),
        client_credential=get_entra_client_secret(),
        authority=authority,
        token_cache=cache,
    )


def get_auth_url(state: str) -> dict:
    """Get the Entra ID authorization URL for the login redirect.

    Args:
        state: CSRF state parameter (random string stored in session).

    Returns:
        dict with 'auth_uri' and 'state' keys.
    """
    app = get_msal_app()
    return app.initiate_auth_code_flow(
        scopes=SCOPES,
        redirect_uri=get_entra_redirect_uri(),
        state=state,
    )


def acquire_token_by_auth_code_flow(
    auth_code_flow: dict,
    auth_response: dict,
    cache: msal.SerializableTokenCache | None = None,
) -> dict:
    """Exchange authorization code for tokens.

    Args:
        auth_code_flow: The flow dict returned by get_auth_url().
        auth_response: The query parameters from the callback URL.
        cache: Optional token cache to populate with the new tokens.

    Returns:
        dict with 'access_token', 'id_token_claims', etc. on success,
        or 'error' key on failure.
    """
    app = get_msal_app(cache=cache)
    return app.acquire_token_by_auth_code_flow(
        auth_code_flow=auth_code_flow,
        auth_response=auth_response,
    )
