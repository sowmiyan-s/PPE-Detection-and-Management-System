"""
Unit tests for EdgeVision Async TTL Caching system.
Verifies caching hits, misses, TTL expiration, tag invalidation, and db helper integration.
"""

import asyncio
import pytest
import time
from src.core.cache import AsyncCacheManager, cached, mongo_cache
from src.core import db

@pytest.mark.asyncio
async def test_cache_manager_basic_get_set():
    cache = AsyncCacheManager()
    await cache.set("key1", {"data": 123}, ttl=5.0, tags=["tag1"])
    
    val = await cache.get("key1")
    assert val == {"data": 123}
    
    metrics = await cache.get_metrics()
    assert metrics["active_entries"] == 1
    assert metrics["total_hits"] == 1
    assert metrics["total_misses"] == 0

@pytest.mark.asyncio
async def test_cache_manager_ttl_expiration():
    cache = AsyncCacheManager()
    await cache.set("short_key", "hello", ttl=0.1, tags=["temp"])
    
    # Immediately available
    val1 = await cache.get("short_key")
    assert val1 == "hello"
    
    # Wait for TTL to expire
    await asyncio.sleep(0.15)
    
    val2 = await cache.get("short_key")
    assert val2 is None
    
    metrics = await cache.get_metrics()
    assert metrics["total_hits"] == 1
    assert metrics["total_misses"] == 1
    assert metrics["active_entries"] == 0

@pytest.mark.asyncio
async def test_tag_invalidation():
    cache = AsyncCacheManager()
    await cache.set("stats_1", {"stats": 10}, ttl=60.0, tags=["stats"])
    await cache.set("stats_2", {"stats": 20}, ttl=60.0, tags=["stats", "reports"])
    await cache.set("zones_1", {"zones": 5}, ttl=60.0, tags=["zones"])
    
    assert await cache.get("stats_1") is not None
    assert await cache.get("stats_2") is not None
    assert await cache.get("zones_1") is not None
    
    # Invalidate stats tag
    count = await cache.invalidate_tags(["stats"])
    assert count == 2
    
    assert await cache.get("stats_1") is None
    assert await cache.get("stats_2") is None
    assert await cache.get("zones_1") is not None

@pytest.mark.asyncio
async def test_cached_decorator():
    call_count = 0

    @cached(ttl=5.0, tags=["test_fn"])
    async def sample_async_func(param: str):
        nonlocal call_count
        call_count += 1
        return f"result_{param}_{call_count}"

    # First call -> executes function
    res1 = await sample_async_func("foo")
    assert res1 == "result_foo_1"
    assert call_count == 1

    # Second call -> cache hit
    res2 = await sample_async_func("foo")
    assert res2 == "result_foo_1"
    assert call_count == 1

    # Call with different arg -> executes function
    res3 = await sample_async_func("bar")
    assert res3 == "result_bar_2"
    assert call_count == 2

    # Invalidate tag -> forces re-execution
    await mongo_cache.invalidate_tags(["test_fn"])
    res4 = await sample_async_func("foo")
    assert res4 == "result_foo_3"
    assert call_count == 3

@pytest.mark.asyncio
async def test_db_caching_and_invalidation():
    await mongo_cache.clear()
    
    # Call get_stats twice
    s1 = await db.get_stats()
    metrics1 = await mongo_cache.get_metrics()
    
    s2 = await db.get_stats()
    metrics2 = await mongo_cache.get_metrics()
    
    assert metrics2["total_hits"] > metrics1["total_hits"]
    assert s1 == s2
    
    # Trigger a violation recording -> should invalidate stats cache
    wid = f"TEST-CACHE-{int(time.time())}"
    await db.record_violation(
        worker_id=wid,
        zone_id="ZONE-01",
        violation_type="Test Missing Helmet",
        detected_ppe=[],
        missing_ppe=["helmet"],
        confidence=0.99
    )
    
    metrics3 = await mongo_cache.get_metrics()
    assert metrics3["total_invalidations"] > 0
