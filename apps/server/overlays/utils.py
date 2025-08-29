from __future__ import annotations

import asyncio
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


async def cleanup_redis_connections(
    redis_conn: redis.Redis | None,
    pubsub_conn: redis.client.PubSub | None,
    redis_task: asyncio.Task | None,
) -> None:
    """
    Clean up Redis connections and tasks gracefully.
    
    Args:
        redis_conn: Redis connection to close
        pubsub_conn: Redis pubsub connection to unsubscribe and close
        redis_task: Asyncio task to cancel
    """
    # Cancel Redis listener task
    if redis_task:
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            pass

    # Close Redis pub/sub connections
    if pubsub_conn:
        try:
            await pubsub_conn.unsubscribe()
            await pubsub_conn.close()
        except (redis.ConnectionError, redis.RedisError) as e:
            logger.warning(f"Error closing Redis pubsub: {e}")
        except Exception as e:
            logger.error(f"Unexpected error closing Redis pubsub: {e}")

    # Close Redis connection
    if redis_conn:
        try:
            await redis_conn.close()
        except (redis.ConnectionError, redis.RedisError) as e:
            logger.warning(f"Error closing Redis connection: {e}")
        except Exception as e:
            logger.error(f"Unexpected error closing Redis connection: {e}")