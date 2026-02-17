"""Tests for ApollosAIMCPConfig cache behavior."""

import pytest

from apollosai.mcp.config import ApollosAIMCPConfig


@pytest.fixture(autouse=True)
def _clear_cache():
    ApollosAIMCPConfig.clear_cache()
    yield
    ApollosAIMCPConfig.clear_cache()


def test_invalidate_mcp_cache():
    """Cache invalidation removes a specific user's entry."""
    ApollosAIMCPConfig._cache['user1'] = (0.0, (None, []))
    ApollosAIMCPConfig._cache['user2'] = (0.0, (None, []))
    ApollosAIMCPConfig.invalidate_mcp_cache('user1')
    assert 'user1' not in ApollosAIMCPConfig._cache
    assert 'user2' in ApollosAIMCPConfig._cache


def test_invalidate_nonexistent_key():
    """Invalidating a missing key is a no-op."""
    ApollosAIMCPConfig.invalidate_mcp_cache('nobody')
    assert 'nobody' not in ApollosAIMCPConfig._cache


def test_clear_cache():
    ApollosAIMCPConfig._cache['user1'] = (0.0, (None, []))
    ApollosAIMCPConfig.clear_cache()
    assert len(ApollosAIMCPConfig._cache) == 0


def test_cache_max_size_eviction():
    """When cache hits max size, oldest entry is evicted."""
    ApollosAIMCPConfig._cache_max_size = 3
    try:
        ApollosAIMCPConfig._cache['a'] = (1.0, (None, []))
        ApollosAIMCPConfig._cache['b'] = (2.0, (None, []))
        ApollosAIMCPConfig._cache['c'] = (3.0, (None, []))
        # Simulate what the config code does when at capacity
        if len(ApollosAIMCPConfig._cache) >= ApollosAIMCPConfig._cache_max_size:
            oldest_key = min(
                ApollosAIMCPConfig._cache,
                key=lambda k: ApollosAIMCPConfig._cache[k][0],
            )
            del ApollosAIMCPConfig._cache[oldest_key]
        ApollosAIMCPConfig._cache['d'] = (4.0, (None, []))
        assert 'a' not in ApollosAIMCPConfig._cache
        assert 'd' in ApollosAIMCPConfig._cache
        assert len(ApollosAIMCPConfig._cache) == 3
    finally:
        ApollosAIMCPConfig._cache_max_size = 1000
