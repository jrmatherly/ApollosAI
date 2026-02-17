from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


async def check_db_health(session_maker: async_sessionmaker) -> bool:
    """Check database connectivity with a simple SELECT 1."""
    try:
        async with session_maker() as session:
            await session.execute(text('SELECT 1'))
        return True
    except Exception:
        return False


async def check_redis_health(redis_client=None) -> bool | None:
    """Check Redis connectivity. Returns None if Redis not configured."""
    import os

    redis_url = os.environ.get('REDIS_URL')
    if not redis_url and redis_client is None:
        return None
    try:
        if redis_client is not None:
            await redis_client.ping()
            return True
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url)
        try:
            await client.ping()
            return True
        finally:
            await client.aclose()
    except Exception:
        return False
