"""
High-Performance In-Memory TTL Cache Engine for EdgeVision MongoDB backend.
Provides async-safe TTL caching, tag-based auto-invalidation, hit/miss metrics,
and decorator-based wrapping for MongoDB read queries.
"""

from __future__ import annotations

import asyncio
import time
import logging
import functools
import json
from typing import Any, Callable, TypeVar, Coroutine

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])

class CacheItem:
    __slots__ = ("value", "expires_at", "tags", "created_at")

    def __init__(self, value: Any, ttl: float, tags: set[str] | None = None) -> None:
        self.value = value
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl
        self.tags: set[str] = tags or set()

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class AsyncCacheManager:
    """In-memory async cache manager with TTL expiration & tag invalidation."""

    def __init__(self) -> None:
        self._cache: dict[str, CacheItem] = {}
        self._tag_map: dict[str, set[str]] = {}  # tag -> set of cache keys
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    async def get(self, key: str) -> Any | None:
        """Retrieve cached value if present and non-expired."""
        async with self._lock:
            item = self._cache.get(key)
            if item is None:
                self._misses += 1
                return None

            if item.is_expired():
                self._misses += 1
                self._remove_key_locked(key)
                return None

            self._hits += 1
            return item.value

    async def set(self, key: str, value: Any, ttl: float, tags: list[str] | None = None) -> None:
        """Store value in cache with TTL (seconds) and optional tags."""
        async with self._lock:
            tag_set = set(tags or [])
            item = CacheItem(value=value, ttl=ttl, tags=tag_set)
            self._cache[key] = item

            for tag in tag_set:
                if tag not in self._tag_map:
                    self._tag_map[tag] = set()
                self._tag_map[tag].add(key)

    async def invalidate_tags(self, tags: list[str]) -> int:
        """Invalidate all cached items associated with any of the provided tags."""
        count = 0
        async with self._lock:
            keys_to_remove: set[str] = set()
            for tag in tags:
                if tag in self._tag_map:
                    keys_to_remove.update(self._tag_map[tag])
                    del self._tag_map[tag]

            for key in keys_to_remove:
                if key in self._cache:
                    self._remove_key_locked(key)
                    count += 1

            self._invalidations += count
        if count > 0:
            log.info("Invalidated %d cache entries for tags: %s", count, tags)
        return count

    async def clear(self) -> None:
        """Purge all cached entries."""
        async with self._lock:
            self._cache.clear()
            self._tag_map.clear()
            self._hits = 0
            self._misses = 0

    def _remove_key_locked(self, key: str) -> None:
        item = self._cache.pop(key, None)
        if item:
            for tag in item.tags:
                if tag in self._tag_map:
                    self._tag_map[tag].discard(key)
                    if not self._tag_map[tag]:
                        del self._tag_map[tag]

    async def get_metrics(self) -> dict[str, Any]:
        """Return cache hit/miss statistics and storage metrics."""
        async with self._lock:
            total_requests = self._hits + self._misses
            hit_ratio = round((self._hits / total_requests * 100), 2) if total_requests > 0 else 0.0
            return {
                "active_entries": len(self._cache),
                "active_tags": list(self._tag_map.keys()),
                "total_hits": self._hits,
                "total_misses": self._misses,
                "hit_ratio_percent": hit_ratio,
                "total_invalidations": self._invalidations,
            }


# Global cache manager instance
mongo_cache = AsyncCacheManager()


def _default_key_builder(func_name: str, args: tuple, kwargs: dict) -> str:
    """Build a deterministic cache key string from function name and arguments."""
    try:
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
    except Exception:
        kwargs_str = str(kwargs)
    args_str = ":".join(str(a) for a in args)
    return f"{func_name}:{args_str}:{kwargs_str}"


def cached(ttl: float = 10.0, tags: list[str] | None = None) -> Callable[[F], F]:
    """Decorator to cache async function results in mongo_cache for `ttl` seconds."""
    tag_list = tags or []

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = _default_key_builder(func.__name__, args, kwargs)
            cached_val = await mongo_cache.get(cache_key)
            if cached_val is not None:
                return cached_val

            # Cache miss — execute query
            res = await func(*args, **kwargs)
            if res is not None:
                await mongo_cache.set(cache_key, res, ttl=ttl, tags=tag_list)
            return res

        return wrapper  # type: ignore

    return decorator
