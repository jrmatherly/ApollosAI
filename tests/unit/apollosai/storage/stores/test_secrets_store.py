from apollosai.storage.stores.secrets_store import ApollosAISecretsStore
from openhands.storage.secrets.secrets_store import SecretsStore


def test_is_subclass_of_secrets_store():
    assert issubclass(ApollosAISecretsStore, SecretsStore)


def test_has_required_methods():
    assert hasattr(ApollosAISecretsStore, 'load')
    assert hasattr(ApollosAISecretsStore, 'store')
    assert hasattr(ApollosAISecretsStore, 'get_instance')
