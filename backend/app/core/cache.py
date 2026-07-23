from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

DASHBOARD_SUMMARY_KEY = "dashboard:summary"

async_redis_client = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
sync_redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def invalidate_dashboard_summary_cache() -> None:
    try:
        sync_redis_client.delete(DASHBOARD_SUMMARY_KEY)
    except Exception:
        # Cache invalidation failures should not break API write operations.
        pass
