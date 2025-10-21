import json
import hashlib
from functools import wraps
from typing import Any, Optional, Callable, List
import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)

class DistributedCache:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            logger.info("Connected to Redis cache.")
        except Exception as e:
            logger.error("Failed to connect to Redis.", error=str(e))
            self.redis = None

    def _generate_cache_key(self, prefix: str, func: Callable, *args, **kwargs) -> str:
        """Generates a consistent cache key."""
        key_parts = f"{prefix}:{func.__module__}:{func.__name__}:{args}:{sorted(kwargs.items())}"
        return f"{prefix}:{hashlib.md5(key_parts.encode()).hexdigest()}"

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis: return None
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error("Cache GET error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int):
        if not self.redis: return
        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
        except Exception as e:
            logger.error("Cache SET error", key=key, error=str(e))

    def cached(self, ttl: int = 3600, key_prefix: str = "cache"):
        """Decorator to cache function results."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                key = self._generate_cache_key(key_prefix, func, *args, **kwargs)
                
                cached_result = await self.get(key)
                if cached_result is not None:
                    logger.debug("Cache hit", key=key)
                    return cached_result
                
                logger.debug("Cache miss", key=key)
                result = await func(*args, **kwargs)
                await self.set(key, result, ttl)
                return result
            return wrapper
        return decorator

class TagBasedCache(DistributedCache):
    """Extends the cache with tag-based invalidation."""
    
    TAG_PREFIX = "tag:"

    async def set_with_tags(self, key: str, value: Any, tags: List[str], ttl: int):
        """Sets a value in the cache and associates it with tags."""
        if not self.redis: return
        
        await self.set(key, value, ttl)
        try:
            # Use a pipeline for atomic operations
            async with self.redis.pipeline() as pipe:
                for tag in tags:
                    tag_key = f"{self.TAG_PREFIX}{tag}"
                    pipe.sadd(tag_key, key)
                    # Give tags a longer TTL than the keys they track
                    pipe.expire(tag_key, ttl + 86400) 
                await pipe.execute()
        except Exception as e:
            logger.error("Cache SET with tags error", key=key, tags=tags, error=str(e))

    async def invalidate_by_tags(self, tags: List[str]):
        """Invalidates all cache keys associated with the given tags."""
        if not self.redis: return
        
        tag_keys = [f"{self.TAG_PREFIX}{tag}" for tag in tags]
        keys_to_invalidate = await self.redis.sunion(tag_keys)
        
        if not keys_to_invalidate:
            return

        try:
            async with self.redis.pipeline() as pipe:
                # Delete the actual cached items
                pipe.delete(*keys_to_invalidate)
                # Delete the tag sets themselves
                pipe.delete(*tag_keys)
                await pipe.execute()
            logger.info("Cache invalidated by tags", tags=tags, invalidated_keys=len(keys_to_invalidate))
        except Exception as e:
            logger.error("Cache invalidation error", tags=tags, error=str(e))

# Example Usage:
#
# cache = TagBasedCache()
#
# @cache.cached(ttl=600)
# async def get_user_profile(user_id: str):
#     # ... fetch from DB
#     return profile
#
# async def update_user_profile(user_id: str, data: dict):
#     # ... update DB
#     await cache.invalidate_by_tags([f"user:{user_id}"])
