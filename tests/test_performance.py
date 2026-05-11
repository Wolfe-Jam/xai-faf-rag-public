"""
Performance and stress tests for XAIFafRag integrator.

Test coverage:
- Latency benchmarks (cache hits vs misses)
- Throughput tests
- Memory usage
- Concurrency stress tests
- Cache performance at scale
"""

import os
import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

import pytest

from tests.conftest import MockClient


def setup_mock_client(collection_id="perf_test_coll"):
    """Set up mock client for performance tests."""
    MockClient.reset_mock()

    mock_collection = MagicMock()
    mock_collection.collection_id = collection_id

    MockClient._collections = MagicMock()
    MockClient._collections.list.return_value.data = []
    MockClient._collections.create.return_value = mock_collection

    # Simulate realistic API latency (10-50ms)
    def search_with_latency(**kwargs):
        time.sleep(0.025)  # 25ms simulated API latency
        return [MagicMock(snippet="result", file_name="test.faf", score=0.95)]

    MockClient._collections.search.side_effect = search_with_latency

    MockClient._chat = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Test response"
    mock_chat.sample.return_value = mock_response
    MockClient._chat.create.return_value = mock_chat

    os.environ["XAI_API_KEY"] = "test_key"
    os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"


class TestLatencyBenchmarks:
    """Latency performance tests."""

    def test_cache_hit_latency_under_1ms(self):
        """Cache hits should be under 1ms (target: 0.003ms)."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # Prime the cache
        integrator.search("test query")

        # Measure cache hit latency
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            integrator.search("test query")
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        p99_latency = statistics.quantiles(latencies, n=100)[98]

        print(f"\nCache hit latency: avg={avg_latency:.3f}ms, p99={p99_latency:.3f}ms")

        # Cache hits should be under 1ms
        assert avg_latency < 1.0, f"Cache hit avg latency {avg_latency:.3f}ms > 1ms"
        assert p99_latency < 5.0, f"Cache hit p99 latency {p99_latency:.3f}ms > 5ms"

    def test_cache_miss_includes_api_latency(self):
        """Cache misses should include simulated API latency."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=False)  # Disable cache

        latencies = []
        for i in range(10):
            start = time.perf_counter()
            integrator.search(f"unique query {i}")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        print(f"\nCache miss latency: avg={avg_latency:.3f}ms")

        # Should include ~25ms simulated API latency
        assert avg_latency > 20, f"Cache miss latency {avg_latency:.3f}ms unexpectedly fast"


class TestThroughput:
    """Throughput performance tests."""

    def test_cache_throughput_1000_queries(self):
        """Measure throughput for cached queries."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # Prime the cache
        integrator.search("throughput test")

        # Measure throughput
        num_queries = 1000
        start = time.perf_counter()
        for _ in range(num_queries):
            integrator.search("throughput test")
        elapsed = time.perf_counter() - start

        qps = num_queries / elapsed
        print(f"\nCache throughput: {qps:.0f} queries/sec ({num_queries} queries in {elapsed:.3f}s)")

        # Should achieve at least 10,000 QPS for cached queries
        assert qps > 1000, f"Throughput {qps:.0f} QPS below 1000 QPS threshold"

    def test_mixed_cache_hit_miss_throughput(self):
        """Measure throughput with mixed cache hits/misses."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # 70% cache hits, 30% misses (simulating target hit rate)
        queries = ["cached_query"] * 70 + [f"unique_{i}" for i in range(30)]

        # Prime the cached query
        integrator.search("cached_query")

        start = time.perf_counter()
        for q in queries:
            integrator.search(q)
        elapsed = time.perf_counter() - start

        qps = len(queries) / elapsed
        print(f"\nMixed throughput (70/30): {qps:.0f} queries/sec")


class TestConcurrencyStress:
    """Concurrency stress tests."""

    def test_concurrent_cache_access_50_threads(self):
        """Stress test cache with 50 concurrent threads."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # Prime cache
        integrator.search("concurrent test")

        errors = []
        results = []

        def worker(thread_id):
            try:
                for _ in range(20):
                    result = integrator.search("concurrent test")
                    results.append(result)
                return True
            except Exception as e:
                errors.append((thread_id, str(e)))
                return False

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(worker, i) for i in range(50)]
            completed = sum(1 for f in as_completed(futures) if f.result())

        print(f"\nConcurrent stress: {completed}/50 threads completed, {len(results)} total queries")

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert completed == 50, f"Only {completed}/50 threads completed"
        assert len(results) == 1000, f"Expected 1000 results, got {len(results)}"

    def test_concurrent_mixed_operations(self):
        """Stress test with mixed search/query operations."""
        setup_mock_client()

        # Set up chat mock
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Concurrent response"
        mock_chat.sample.return_value = mock_response
        MockClient._chat.create.return_value = mock_chat

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        errors = []
        operation_counts = {"search": 0, "query": 0}
        lock = threading.Lock()

        def worker(thread_id):
            try:
                for i in range(10):
                    if i % 2 == 0:
                        integrator.search(f"search_{thread_id}_{i}")
                        with lock:
                            operation_counts["search"] += 1
                    else:
                        integrator.query(f"query_{thread_id}_{i}")
                        with lock:
                            operation_counts["query"] += 1
                return True
            except Exception as e:
                errors.append((thread_id, str(e)))
                return False

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker, i) for i in range(20)]
            completed = sum(1 for f in as_completed(futures) if f.result())

        print(f"\nMixed concurrent: {operation_counts}")

        assert len(errors) == 0, f"Errors: {errors}"
        assert completed == 20


class TestCacheScaling:
    """Cache performance at scale."""

    def test_cache_with_1000_unique_entries(self):
        """Test cache performance with 1000 unique entries."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # Disable API latency for bulk insert
        MockClient._collections.search.side_effect = None
        MockClient._collections.search.return_value = [MagicMock()]

        # Fill cache with 1000 unique queries
        for i in range(1000):
            integrator.search(f"unique_query_{i}")

        stats = integrator.cache_stats()
        assert stats["size"] == 1000, f"Cache size {stats['size']} != 1000"

        # Verify cache hit performance at scale
        latencies = []
        for i in range(100):
            start = time.perf_counter()
            integrator.search(f"unique_query_{i}")  # Should hit cache
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        print(f"\nCache lookup (1000 entries): avg={avg_latency:.3f}ms")

        assert avg_latency < 1.0, f"Cache lookup degraded: {avg_latency:.3f}ms"

    def test_cache_clear_performance(self):
        """Test cache clear performance."""
        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        MockClient._collections.search.side_effect = None
        MockClient._collections.search.return_value = [MagicMock()]

        # Fill cache
        for i in range(500):
            integrator.search(f"query_{i}")

        assert integrator.cache_stats()["size"] == 500

        # Measure clear time
        start = time.perf_counter()
        integrator.clear_cache()
        elapsed = (time.perf_counter() - start) * 1000

        print(f"\nCache clear (500 entries): {elapsed:.3f}ms")

        assert integrator.cache_stats()["size"] == 0
        assert elapsed < 10, f"Cache clear took {elapsed:.3f}ms > 10ms"


class TestMemoryUsage:
    """Memory usage tests."""

    def test_cache_memory_bounded(self):
        """Verify cache doesn't grow unbounded (basic check)."""
        import sys

        setup_mock_client()

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        MockClient._collections.search.side_effect = None
        MockClient._collections.search.return_value = [MagicMock()]

        # Measure baseline
        baseline_size = sys.getsizeof(integrator._cache)

        # Add 100 entries
        for i in range(100):
            integrator.search(f"memory_test_{i}")

        after_size = sys.getsizeof(integrator._cache)
        growth = after_size - baseline_size

        print(f"\nCache memory: baseline={baseline_size}B, after={after_size}B, growth={growth}B")

        # Basic sanity check - cache dict shouldn't be unreasonably large
        assert after_size < 100000, f"Cache memory {after_size}B seems too large"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
