from apollosai.storage.stores.settings_store import ApollosAISettingsStore
from openhands.storage.settings.settings_store import SettingsStore


def test_is_subclass_of_settings_store():
    assert issubclass(ApollosAISettingsStore, SettingsStore)


def test_has_required_methods():
    assert hasattr(ApollosAISettingsStore, 'load')
    assert hasattr(ApollosAISettingsStore, 'store')
    assert hasattr(ApollosAISettingsStore, 'get_instance')
