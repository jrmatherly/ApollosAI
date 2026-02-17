"""Tests for env-driven branding fields in WebClientConfig."""

import pytest

from openhands.app_server.web_client.default_web_client_config_injector import (
    DefaultWebClientConfigInjector,
)
from openhands.app_server.web_client.web_client_models import WebClientConfig
from openhands.server.types import AppMode


@pytest.fixture(autouse=True)
def _clear_branding_env(monkeypatch):
    """Ensure branding env vars are unset by default."""
    for var in (
        'APP_DISPLAY_NAME',
        'APP_LOGO_URL',
        'APP_PRIMARY_COLOR',
        'APP_FAVICON_URL',
    ):
        monkeypatch.delenv(var, raising=False)


def test_branding_fields_default_to_none():
    """Branding fields should be None when env vars are not set."""
    injector = DefaultWebClientConfigInjector()
    assert injector.app_display_name is None
    assert injector.app_logo_url is None
    assert injector.app_primary_color is None
    assert injector.app_favicon_url is None


def test_branding_fields_read_from_env(monkeypatch):
    """Branding fields should pick up values from environment variables."""
    monkeypatch.setenv('APP_DISPLAY_NAME', 'ApollosAI')
    monkeypatch.setenv('APP_LOGO_URL', 'https://example.com/logo.png')
    monkeypatch.setenv('APP_PRIMARY_COLOR', '#1a73e8')
    monkeypatch.setenv('APP_FAVICON_URL', 'https://example.com/favicon.ico')

    injector = DefaultWebClientConfigInjector()
    assert injector.app_display_name == 'ApollosAI'
    assert injector.app_logo_url == 'https://example.com/logo.png'
    assert injector.app_primary_color == '#1a73e8'
    assert injector.app_favicon_url == 'https://example.com/favicon.ico'


@pytest.mark.asyncio
async def test_get_web_client_config_passes_branding(monkeypatch):
    """get_web_client_config() must propagate branding fields to WebClientConfig."""
    monkeypatch.setenv('APP_DISPLAY_NAME', 'TestApp')
    monkeypatch.setenv('APP_LOGO_URL', '/static/logo.svg')
    monkeypatch.setenv('APP_PRIMARY_COLOR', 'rgb(0, 120, 212)')
    monkeypatch.setenv('APP_FAVICON_URL', '/favicon.ico')

    # Patch global config to avoid import-time side effects
    monkeypatch.setattr(
        'openhands.app_server.config.get_global_config',
        lambda: type('C', (), {'app_mode': AppMode.OPENHANDS})(),
    )

    injector = DefaultWebClientConfigInjector()
    config = await injector.get_web_client_config()

    assert isinstance(config, WebClientConfig)
    assert config.app_display_name == 'TestApp'
    assert config.app_logo_url == '/static/logo.svg'
    assert config.app_primary_color == 'rgb(0, 120, 212)'
    assert config.app_favicon_url == '/favicon.ico'


def test_web_client_config_model_accepts_branding_fields():
    """WebClientConfig model should accept all branding fields."""
    config = WebClientConfig(
        app_mode=AppMode.OPENHANDS,
        posthog_client_key=None,
        feature_flags={'enable_billing': False},
        providers_configured=[],
        maintenance_start_time=None,
        auth_url=None,
        recaptcha_site_key=None,
        faulty_models=[],
        error_message=None,
        updated_at='2026-01-01T00:00:00Z',
        github_app_slug=None,
        app_display_name='MyApp',
        app_logo_url='https://example.com/logo.png',
        app_primary_color='#ff0000',
        app_favicon_url='/favicon.ico',
    )
    assert config.app_display_name == 'MyApp'
    assert config.app_logo_url == 'https://example.com/logo.png'
    assert config.app_primary_color == '#ff0000'
    assert config.app_favicon_url == '/favicon.ico'
