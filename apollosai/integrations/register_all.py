"""Auto-register all integration managers at startup."""

from apollosai.integrations.bitbucket.manager import BitbucketIntegrationManager
from apollosai.integrations.github.manager import GitHubIntegrationManager
from apollosai.integrations.jira.manager import JiraIntegrationManager
from apollosai.integrations.microsoft.manager import MicrosoftIntegrationManager
from apollosai.integrations.models import IntegrationType
from apollosai.integrations.registry import register_integration
from apollosai.integrations.slack.manager import SlackIntegrationManager


def register_all_integrations() -> None:
    """Register all platform integration managers."""
    register_integration(IntegrationType.GITHUB, GitHubIntegrationManager)
    register_integration(IntegrationType.JIRA, JiraIntegrationManager)
    register_integration(IntegrationType.SLACK, SlackIntegrationManager)
    register_integration(IntegrationType.BITBUCKET, BitbucketIntegrationManager)
    register_integration(IntegrationType.MICROSOFT, MicrosoftIntegrationManager)
