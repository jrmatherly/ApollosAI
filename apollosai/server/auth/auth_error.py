"""Authentication error hierarchy for ApollosAI.

Clean-room implementation — enterprise defines similar errors at
enterprise/server/auth/auth_error.py but we cannot import from there
(PolyForm license) and they are not in openhands/ core.
"""


class AuthError(Exception):
    """Base authentication error."""

    pass


class NoCredentialsError(AuthError):
    """No authentication credentials were provided."""

    pass


class InvalidTokenError(AuthError):
    """Raised when a provided token fails validation (expired, tampered, wrong signature)."""

    pass


class ExpiredError(AuthError):
    """Authentication token has expired."""

    pass
