from fastapi import APIRouter
from fastapi.responses import JSONResponse

from apollosai.monitoring.health import check_db_health, check_redis_health
from apollosai.server.lifespan import get_session_maker

router = APIRouter()


@router.get('/health')
async def health():
    """Liveness probe — returns 200 if process is running."""
    return {'status': 'ok'}


@router.get('/ready')
async def ready():
    """Readiness probe — checks DB and Redis connectivity."""
    session_maker = get_session_maker()
    if session_maker is None:
        return JSONResponse(
            status_code=503,
            content={
                'status': 'not_ready',
                'error': 'Database not initialized',
            },
        )

    db_ok = await check_db_health(session_maker)
    redis_result = await check_redis_health()

    checks: dict[str, bool] = {'database': db_ok}
    if redis_result is not None:
        checks['redis'] = redis_result

    all_ok = db_ok and (redis_result is None or redis_result)

    if not all_ok:
        return JSONResponse(
            status_code=503,
            content={'status': 'not_ready', 'checks': checks},
        )
    return {'status': 'ready', 'checks': checks}
