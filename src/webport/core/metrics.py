"""
WebPort Metrics System

Statistics tracking and Prometheus export.

Addresses Critique #14: Missing Crawl Statistics/Metrics
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from contextlib import contextmanager

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server, REGISTRY
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

logger = logging.getLogger(__name__)


@dataclass
class CrawlMetrics:
    """Crawl statistics."""
    
    # Counters
    pages_crawled: int = 0
    pages_failed: int = 0
    pages_skipped: int = 0
    bytes_downloaded: int = 0
    requests_total: int = 0
    requests_retried: int = 0
    
    # Rates
    pages_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
    # Timing
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    total_request_time_ms: float = 0.0
    
    # Per-domain stats
    domain_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Status code distribution
    status_codes: Dict[int, int] = field(default_factory=dict)
    
    # Error distribution
    error_types: Dict[str, int] = field(default_factory=dict)
    
    # Queue stats
    queue_depth: int = 0
    queue_max_depth: int = 0
    
    # Latency percentiles
    latencies: List[float] = field(default_factory=list)
    max_latencies: int = 1000
    
    def record_request(
        self,
        url: str,
        status_code: int,
        bytes_size: int,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record a request."""
        from urllib.parse import urlparse
        
        self.requests_total += 1
        self.bytes_downloaded += bytes_size
        self.total_request_time_ms += latency_ms
        
        if success:
            self.pages_crawled += 1
        else:
            self.pages_failed += 1
        
        # Status code
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        
        # Domain stats
        domain = urlparse(url).netloc
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {"requests": 0, "bytes": 0, "errors": 0}
        self.domain_stats[domain]["requests"] += 1
        self.domain_stats[domain]["bytes"] += bytes_size
        if not success:
            self.domain_stats[domain]["errors"] += 1
        
        # Error type
        if error:
            error_type = error.split(":")[0] if ":" in error else error
            self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
        
        # Latency tracking
        if len(self.latencies) < self.max_latencies:
            self.latencies.append(latency_ms)
        
        # Update rates
        self._update_rates()
    
    def record_queue_depth(self, depth: int) -> None:
        """Record queue depth."""
        self.queue_depth = depth
        self.queue_max_depth = max(self.queue_max_depth, depth)
    
    def _update_rates(self) -> None:
        """Update rate calculations."""
        now = datetime.utcnow()
        self.last_update = now
        
        if self.start_time:
            elapsed = (now - self.start_time).total_seconds()
            if elapsed > 0:
                self.pages_per_second = self.pages_crawled / elapsed
                self.bytes_per_second = self.bytes_downloaded / elapsed
    
    @property
    def avg_latency_ms(self) -> float:
        """Average request latency."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)
    
    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    @property
    def success_rate(self) -> float:
        """Success rate percentage."""
        total = self.pages_crawled + self.pages_failed
        if total == 0:
            return 100.0
        return (self.pages_crawled / total) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        """Elapsed time since start."""
        if not self.start_time:
            return 0.0
        end = self.last_update or datetime.utcnow()
        return (end - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pages_crawled": self.pages_crawled,
            "pages_failed": self.pages_failed,
            "bytes_downloaded": self.bytes_downloaded,
            "pages_per_second": round(self.pages_per_second, 2),
            "success_rate": round(self.success_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "queue_depth": self.queue_depth,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "status_codes": self.status_codes,
            "error_types": self.error_types,
        }
    
    def report(self) -> str:
        """Generate text report."""
        return f"""
{'='*60}
CRAWL METRICS
{'='*60}
Pages Crawled:    {self.pages_crawled}
Pages Failed:     {self.pages_failed}
Success Rate:     {self.success_rate:.1f}%
Bytes Downloaded: {self.bytes_downloaded / 1024 / 1024:.2f} MB
Pages/Second:     {self.pages_per_second:.2f}
Avg Latency:      {self.avg_latency_ms:.0f} ms
P95 Latency:      {self.p95_latency_ms:.0f} ms
Queue Depth:      {self.queue_depth}
Elapsed Time:     {self.elapsed_seconds:.1f}s

Status Codes:
{self._format_dict(self.status_codes)}

Error Types:
{self._format_dict(self.error_types)}
"""
    
    def _format_dict(self, d: Dict) -> str:
        if not d:
            return "  (none)"
        return "\n".join(f"  {k}: {v}" for k, v in sorted(d.items(), key=lambda x: -x[1]))


class MetricsCollector:
    """
    Central metrics collection with optional Prometheus export.
    """
    
    _instance: Optional["MetricsCollector"] = None
    
    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, prometheus_enabled: bool = False, prometheus_port: int = 9090):
        if self._initialized:
            return
        
        self.metrics = CrawlMetrics()
        self.prometheus_enabled = prometheus_enabled and HAS_PROMETHEUS
        self.prometheus_port = prometheus_port
        self._lock = threading.Lock()
        self._initialized = True
        
        if self.prometheus_enabled:
            self._init_prometheus()
    
    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        self.prom_pages_crawled = Counter(
            "webport_pages_crawled_total",
            "Total pages crawled"
        )
        self.prom_pages_failed = Counter(
            "webport_pages_failed_total",
            "Total pages failed"
        )
        self.prom_bytes_downloaded = Counter(
            "webport_bytes_downloaded_total",
            "Total bytes downloaded"
        )
        self.prom_request_latency = Histogram(
            "webport_request_latency_seconds",
            "Request latency in seconds",
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        self.prom_queue_depth = Gauge(
            "webport_queue_depth",
            "Current queue depth"
        )
        
        # Start Prometheus HTTP server
        try:
            start_http_server(self.prometheus_port)
            logger.info(f"Prometheus metrics available on port {self.prometheus_port}")
        except Exception as e:
            logger.warning(f"Failed to start Prometheus server: {e}")
    
    def record_request(
        self,
        url: str,
        status_code: int,
        bytes_size: int,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record a request."""
        with self._lock:
            self.metrics.record_request(url, status_code, bytes_size, latency_ms, success, error)
        
        # Update Prometheus
        if self.prometheus_enabled:
            if success:
                self.prom_pages_crawled.inc()
            else:
                self.prom_pages_failed.inc()
            self.prom_bytes_downloaded.inc(bytes_size)
            self.prom_request_latency.observe(latency_ms / 1000)
    
    def record_queue_depth(self, depth: int) -> None:
        """Record queue depth."""
        with self._lock:
            self.metrics.record_queue_depth(depth)
        
        if self.prometheus_enabled:
            self.prom_queue_depth.set(depth)
    
    def start(self) -> None:
        """Start metrics collection."""
        with self._lock:
            self.metrics.start_time = datetime.utcnow()
    
    def get_metrics(self) -> CrawlMetrics:
        """Get current metrics."""
        return self.metrics
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.metrics = CrawlMetrics()


@contextmanager
def timed_operation(name: str, collector: Optional[MetricsCollector] = None):
    """Context manager for timing operations."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug(f"{name} completed in {duration_ms:.2f}ms")


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return MetricsCollector()


__all__ = [
    "CrawlMetrics",
    "MetricsCollector",
    "timed_operation",
    "get_metrics_collector",
]
