"""Tests for ApollosAIMCPConfig cache behavior."""

import time

import pytest
from cachetools import TTLCache

from apollosai.mcp.config import ApollosAIMCPConfig


@pytest.fixture(autouse=True)
def _clear_cache():
    ApollosAIMCPConfig.clear_cache()
    yield
    ApollosAIMCPConfig.clear_cache()


def test_invalidate_mcp_cache():
    """Cache invalidation removes a specific user's entry."""
    ApollosAIMCPConfig._cache['user1'] = (None, [])
    ApollosAIMCPConfig._cache['user2'] = (None, [])
    ApollosAIMCPConfig.invalidate_mcp_cache('user1')
    assert 'user1' not in ApollosAIMCPConfig._cache
    assert 'user2' in ApollosAIMCPConfig._cache


def test_invalidate_nonexistent_key():
    """Invalidating a missing key is a no-op."""
    ApollosAIMCPConfig.invalidate_mcp_cache('nobody')
    assert 'nobody' not in ApollosAIMCPConfig._cache


def test_clear_cache():
    ApollosAIMCPConfig._cache['user1'] = (None, [])
    ApollosAIMCPConfig.clear_cache()
    assert len(ApollosAIMCPConfig._cache) == 0


def test_cache_is_ttl_cache():
    """H6: Cache must be a TTLCache for automatic expiry."""
    assert isinstance(ApollosAIMCPConfig._cache, TTLCache)


def test_cache_ttl_expiry(monkeypatch):
    """H6: Verify stale entries are evicted after TTL."""
    # Create a short-lived TTLCache for testing
    original_cache = ApollosAIMCPConfig._cache
    test_cache = TTLCache(maxsize=100, ttl=1)
    ApollosAIMCPConfig._cache = test_cache
    try:
        ApollosAIMCPConfig._cache['user1'] = (None, [])
        assert 'user1' in ApollosAIMCPConfig._cache
        # Wait for TTL to expire
        time.sleep(1.1)
        assert 'user1' not in ApollosAIMCPConfig._cache
    finally:
        ApollosAIMCPConfig._cache = original_cache


def test_cache_max_size_eviction():
    """TTLCache respects maxsize and evicts LRU entries."""
    original_cache = ApollosAIMCPConfig._cache
    test_cache = TTLCache(maxsize=3, ttl=300)
    ApollosAIMCPConfig._cache = test_cache
    try:
        ApollosAIMCPConfig._cache['a'] = (None, [])
        ApollosAIMCPConfig._cache['b'] = (None, [])
        ApollosAIMCPConfig._cache['c'] = (None, [])
        # Adding a 4th entry should evict the least recently used
        ApollosAIMCPConfig._cache['d'] = (None, [])
        assert 'a' not in ApollosAIMCPConfig._cache
        assert 'd' in ApollosAIMCPConfig._cache
        assert len(ApollosAIMCPConfig._cache) == 3
    finally:
        ApollosAIMCPConfig._cache = original_cache


def test_create_default_is_classmethod():
    """L5: create_default_mcp_server_config must be a classmethod, not staticmethod."""
    assert isinstance(
        ApollosAIMCPConfig.__dict__['create_default_mcp_server_config'],
        classmethod,
    )
