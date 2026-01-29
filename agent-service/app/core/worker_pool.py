"""
Async Worker Pool for High-Throughput Event Processing

Provides parallel processing of Redis events to handle thousands
of concurrent sessions without blocking.

Features:
- Configurable number of workers
- Per-session ordering guarantees
- Backpressure handling
- Graceful shutdown
- Metrics for monitoring

Usage:
    pool = AsyncWorkerPool(num_workers=4, queue_size=1000)
    await pool.start()

    # Submit work
    await pool.submit(session_id, process_event, event_data)

    # Graceful shutdown
    await pool.stop()
"""

import asyncio
import logging
import time
from typing import Dict, Callable, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class WorkerPoolStats:
    """Statistics for worker pool monitoring"""
    total_submitted: int = 0
    total_processed: int = 0
    total_errors: int = 0
    total_dropped: int = 0
    queue_full_events: int = 0
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    started_at: Optional[datetime] = None

    # Per-worker stats
    worker_processed: Dict[int, int] = field(default_factory=dict)
    worker_errors: Dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "total_submitted": self.total_submitted,
            "total_processed": self.total_processed,
            "total_errors": self.total_errors,
            "total_dropped": self.total_dropped,
            "queue_full_events": self.queue_full_events,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "max_processing_time_ms": self.max_processing_time_ms,
            "success_rate": self.total_processed / max(1, self.total_submitted),
            "uptime_seconds": (datetime.now(timezone.utc) - self.started_at).total_seconds() if self.started_at else 0,
            "worker_processed": self.worker_processed,
            "worker_errors": self.worker_errors,
        }


@dataclass
class WorkItem:
    """Represents a unit of work"""
    key: str  # Used for routing to specific worker
    func: Callable
    args: tuple
    kwargs: dict
    submitted_at: float = field(default_factory=time.time)


class AsyncWorkerPool:
    """
    Async worker pool for parallel event processing.

    Features:
    - Consistent hashing for session affinity (events from same session go to same worker)
    - Bounded queues with backpressure
    - Graceful shutdown
    """

    def __init__(
        self,
        num_workers: int = 4,
        queue_size: int = 1000,
        name: str = "event_processor"
    ):
        """
        Initialize worker pool.

        Args:
            num_workers: Number of worker tasks
            queue_size: Max items per worker queue (backpressure when full)
            name: Pool name for logging
        """
        self.num_workers = num_workers
        self.queue_size = queue_size
        self.name = name

        # One queue per worker for session affinity
        self.queues: List[asyncio.Queue] = []
        self.workers: List[asyncio.Task] = []
        self.running = False
        self.stats = WorkerPoolStats()

        # For calculating average processing time
        self._processing_times: List[float] = []
        self._max_time_samples = 1000

        logger.info(
            f"Worker pool '{name}' initialized: "
            f"workers={num_workers}, queue_size={queue_size}"
        )

    def _get_worker_index(self, key: str) -> int:
        """
        Get worker index for a key using consistent hashing.

        This ensures events for the same session always go to the same worker,
        preserving ordering guarantees.
        """
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return hash_val % self.num_workers

    async def start(self):
        """Start the worker pool."""
        if self.running:
            logger.warning(f"Worker pool '{self.name}' already running")
            return

        self.running = True
        self.stats.started_at = datetime.now(timezone.utc)

        # Create queues and workers
        self.queues = [asyncio.Queue(maxsize=self.queue_size) for _ in range(self.num_workers)]
        self.workers = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(self.num_workers)
        ]

        # Initialize per-worker stats
        for i in range(self.num_workers):
            self.stats.worker_processed[i] = 0
            self.stats.worker_errors[i] = 0

        logger.info(f"Worker pool '{self.name}' started with {self.num_workers} workers")

    async def stop(self, timeout: float = 30.0):
        """
        Stop the worker pool gracefully.

        Args:
            timeout: Max seconds to wait for queues to drain
        """
        if not self.running:
            return

        self.running = False
        logger.info(f"Stopping worker pool '{self.name}'...")

        # Signal workers to stop by putting None in each queue
        for queue in self.queues:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

        # Wait for workers to finish with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.workers, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Worker pool '{self.name}' shutdown timed out, cancelling workers")
            for worker in self.workers:
                worker.cancel()

        logger.info(
            f"Worker pool '{self.name}' stopped. "
            f"Processed: {self.stats.total_processed}, Errors: {self.stats.total_errors}"
        )

    async def submit(
        self,
        key: str,
        func: Callable,
        *args,
        timeout: float = 1.0,
        **kwargs
    ) -> bool:
        """
        Submit work to the pool.

        Args:
            key: Key for routing (e.g., session_id) - same key goes to same worker
            func: Async function to execute
            *args: Arguments for func
            timeout: Max seconds to wait if queue is full
            **kwargs: Keyword arguments for func

        Returns:
            True if submitted, False if dropped (queue full)
        """
        if not self.running:
            logger.warning(f"Worker pool '{self.name}' not running, dropping work")
            return False

        self.stats.total_submitted += 1

        worker_idx = self._get_worker_index(key)
        queue = self.queues[worker_idx]

        work = WorkItem(key=key, func=func, args=args, kwargs=kwargs)

        try:
            await asyncio.wait_for(queue.put(work), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            self.stats.queue_full_events += 1
            self.stats.total_dropped += 1
            logger.warning(
                f"Worker pool '{self.name}' queue {worker_idx} full, "
                f"dropping work for key={key[:8]}..."
            )
            return False

    def submit_nowait(self, key: str, func: Callable, *args, **kwargs) -> bool:
        """
        Submit work without waiting (returns immediately if queue full).

        Args:
            key: Key for routing
            func: Async function to execute
            *args: Arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            True if submitted, False if dropped
        """
        if not self.running:
            return False

        self.stats.total_submitted += 1

        worker_idx = self._get_worker_index(key)
        queue = self.queues[worker_idx]

        work = WorkItem(key=key, func=func, args=args, kwargs=kwargs)

        try:
            queue.put_nowait(work)
            return True
        except asyncio.QueueFull:
            self.stats.queue_full_events += 1
            self.stats.total_dropped += 1
            return False

    async def _worker_loop(self, worker_id: int):
        """Worker loop that processes items from queue."""
        queue = self.queues[worker_id]
        logger.debug(f"Worker {worker_id} started")

        while True:
            try:
                # Get work item
                work = await queue.get()

                # None signals shutdown
                if work is None:
                    break

                # Process work
                start_time = time.time()
                try:
                    if asyncio.iscoroutinefunction(work.func):
                        await work.func(*work.args, **work.kwargs)
                    else:
                        work.func(*work.args, **work.kwargs)

                    self.stats.total_processed += 1
                    self.stats.worker_processed[worker_id] += 1

                except Exception as e:
                    self.stats.total_errors += 1
                    self.stats.worker_errors[worker_id] += 1
                    logger.error(
                        f"Worker {worker_id} error processing {work.key[:8]}...: {e}",
                        exc_info=True
                    )

                # Update timing stats
                processing_time = (time.time() - start_time) * 1000  # ms
                self._update_timing_stats(processing_time)

                queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} unexpected error: {e}", exc_info=True)

        logger.debug(f"Worker {worker_id} stopped")

    def _update_timing_stats(self, processing_time_ms: float):
        """Update processing time statistics."""
        self._processing_times.append(processing_time_ms)

        # Keep only recent samples
        if len(self._processing_times) > self._max_time_samples:
            self._processing_times = self._processing_times[-self._max_time_samples:]

        # Update stats
        self.stats.avg_processing_time_ms = sum(self._processing_times) / len(self._processing_times)
        self.stats.max_processing_time_ms = max(self.stats.max_processing_time_ms, processing_time_ms)

    def get_queue_depths(self) -> List[int]:
        """Get current queue depth for each worker."""
        return [q.qsize() for q in self.queues]

    def get_stats(self) -> Dict:
        """Get worker pool statistics."""
        stats = self.stats.to_dict()
        stats["queue_depths"] = self.get_queue_depths()
        stats["total_queue_depth"] = sum(self.get_queue_depths())
        return stats


# Global worker pool instance
_event_worker_pool: Optional[AsyncWorkerPool] = None


def get_event_worker_pool(
    num_workers: int = 4,
    queue_size: int = 1000
) -> AsyncWorkerPool:
    """Get or create the global event worker pool."""
    global _event_worker_pool
    if _event_worker_pool is None:
        _event_worker_pool = AsyncWorkerPool(
            num_workers=num_workers,
            queue_size=queue_size,
            name="engagement_events"
        )
    return _event_worker_pool


async def init_worker_pool(num_workers: int = 4, queue_size: int = 1000):
    """Initialize and start the global worker pool."""
    pool = get_event_worker_pool(num_workers, queue_size)
    await pool.start()
    return pool


async def shutdown_worker_pool():
    """Shutdown the global worker pool."""
    global _event_worker_pool
    if _event_worker_pool is not None:
        await _event_worker_pool.stop()
        _event_worker_pool = None
