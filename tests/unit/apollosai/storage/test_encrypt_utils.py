import pytest


@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch):
    """Use monkeypatch for test isolation — prevents accidental use of production keys."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'test-key-for-unit-tests-must-be-32chars!')
    # Reset the cached key so each test gets a fresh derivation
    from apollosai.storage.encrypt_utils import reset_key_cache
    reset_key_cache()


def test_encrypt_decrypt_roundtrip():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    original = 'sk-abc123-my-api-key'
    encrypted = encrypt_value(original)
    assert encrypted != original
    decrypted = decrypt_value(encrypted)
    assert decrypted == original


def test_encrypt_different_each_time():
    """AES-GCM with random nonce should produce different ciphertext."""
    from apollosai.storage.encrypt_utils import encrypt_value
    original = 'same-value'
    enc1 = encrypt_value(original)
    enc2 = encrypt_value(original)
    assert enc1 != enc2


def test_decrypt_invalid_raises():
    from apollosai.storage.encrypt_utils import decrypt_value
    with pytest.raises(Exception):
        decrypt_value('not-valid-ciphertext')


def test_encrypt_empty_string():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    encrypted = encrypt_value('')
    assert decrypt_value(encrypted) == ''


def test_encrypt_unicode():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    original = 'unicode: \u2603\u2764\ufe0f \U0001f680'
    encrypted = encrypt_value(original)
    assert decrypt_value(encrypted) == original


def test_encrypt_long_value():
    from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value
    original = 'x' * 10000
    encrypted = encrypt_value(original)
    assert decrypt_value(encrypted) == original


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv('APOLLOSAI_ENCRYPTION_KEY', raising=False)
    from apollosai.storage.encrypt_utils import reset_key_cache, encrypt_value
    reset_key_cache()
    with pytest.raises(ValueError, match='APOLLOSAI_ENCRYPTION_KEY'):
        encrypt_value('test')
