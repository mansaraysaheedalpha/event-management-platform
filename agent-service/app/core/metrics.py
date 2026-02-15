"""
Prometheus Metrics for Engagement Conductor AI

Provides comprehensive observability for:
- Agent decision latency
- Intervention success rates
- Thompson Sampling statistics
- Circuit breaker states
- Rate limiter statistics
- Memory usage
- Queue depths

Usage:
    from app.core.metrics import metrics

    # Record a decision
    with metrics.decision_latency.labels(anomaly_type="SUDDEN_DROP").time():
        # make decision

    # Record intervention
    metrics.interventions_total.labels(type="POLL", outcome="success").inc()
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass
import time
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Counter:
    """Simple thread-safe counter."""
    def __init__(self, name: str, description: str, labels: tuple = ()):
        self.name = name
        self.description = description
        self.label_names = labels
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "LabeledCounter":
        label_values = tuple(kwargs.get(name, "") for name in self.label_names)
        return LabeledCounter(self, label_values)

    def inc(self, value: float = 1.0, labels: tuple = ()):
        with self._lock:
            if labels not in self._values:
                self._values[labels] = 0.0
            self._values[labels] += value

    def get(self, labels: tuple = ()) -> float:
        with self._lock:
            return self._values.get(labels, 0.0)

    def get_all(self) -> Dict[tuple, float]:
        with self._lock:
            return dict(self._values)


class LabeledCounter:
    def __init__(self, counter: Counter, labels: tuple):
        self._counter = counter
        self._labels = labels

    def inc(self, value: float = 1.0):
        self._counter.inc(value, self._labels)


class Gauge:
    """Simple thread-safe gauge."""
    def __init__(self, name: str, description: str, labels: tuple = ()):
        self.name = name
        self.description = description
        self.label_names = labels
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "LabeledGauge":
        label_values = tuple(kwargs.get(name, "") for name in self.label_names)
        return LabeledGauge(self, label_values)

    def set(self, value: float, labels: tuple = ()):
        with self._lock:
            self._values[labels] = value

    def inc(self, value: float = 1.0, labels: tuple = ()):
        with self._lock:
            if labels not in self._values:
                self._values[labels] = 0.0
            self._values[labels] += value

    def dec(self, value: float = 1.0, labels: tuple = ()):
        with self._lock:
            if labels not in self._values:
                self._values[labels] = 0.0
            self._values[labels] -= value

    def get(self, labels: tuple = ()) -> float:
        with self._lock:
            return self._values.get(labels, 0.0)

    def get_all(self) -> Dict[tuple, float]:
        with self._lock:
            return dict(self._values)


class LabeledGauge:
    def __init__(self, gauge: Gauge, labels: tuple):
        self._gauge = gauge
        self._labels = labels

    def set(self, value: float):
        self._gauge.set(value, self._labels)

    def inc(self, value: float = 1.0):
        self._gauge.inc(value, self._labels)

    def dec(self, value: float = 1.0):
        self._gauge.dec(value, self._labels)


class Histogram:
    """Simple histogram for tracking distributions."""
    def __init__(
        self,
        name: str,
        description: str,
        labels: tuple = (),
        buckets: tuple = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    ):
        self.name = name
        self.description = description
        self.label_names = labels
        self.buckets = buckets
        self._values: Dict[tuple, list] = {}
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "LabeledHistogram":
        label_values = tuple(kwargs.get(name, "") for name in self.label_names)
        return LabeledHistogram(self, label_values)

    def observe(self, value: float, labels: tuple = ()):
        with self._lock:
            if labels not in self._values:
                self._values[labels] = []
            self._values[labels].append(value)
            # Keep only last 10000 samples to prevent memory growth
            if len(self._values[labels]) > 10000:
                self._values[labels] = self._values[labels][-10000:]

    @contextmanager
    def time(self, labels: tuple = ()):
        """Context manager to time a block of code."""
        start = time.time()
        try:
            yield
        finally:
            self.observe(time.time() - start, labels)

    def get_stats(self, labels: tuple = ()) -> Dict:
        with self._lock:
            values = self._values.get(labels, [])
            if not values:
                return {"count": 0, "sum": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

            sorted_values = sorted(values)
            count = len(sorted_values)
            return {
                "count": count,
                "sum": sum(sorted_values),
                "avg": sum(sorted_values) / count,
                "p50": sorted_values[min(int(count * 0.5), count - 1)] if count > 0 else 0,
                "p95": sorted_values[min(int(count * 0.95), count - 1)] if count > 0 else 0,
                "p99": sorted_values[min(int(count * 0.99), count - 1)] if count > 0 else 0,
            }


class LabeledHistogram:
    def __init__(self, histogram: Histogram, labels: tuple):
        self._histogram = histogram
        self._labels = labels

    def observe(self, value: float):
        self._histogram.observe(value, self._labels)

    @contextmanager
    def time(self):
        start = time.time()
        try:
            yield
        finally:
            self.observe(time.time() - start)


class EngagementConductorMetrics:
    """
    Centralized metrics for Engagement Conductor AI.
    """

    def __init__(self):
        # Agent Decision Metrics
        self.decision_latency = Histogram(
            name="engagement_conductor_decision_latency_seconds",
            description="Latency of agent decisions",
            labels=("anomaly_type", "intervention_type"),
        )

        self.decisions_total = Counter(
            name="engagement_conductor_decisions_total",
            description="Total agent decisions made",
            labels=("anomaly_type", "intervention_type", "auto_approved"),
        )

        # Intervention Metrics
        self.interventions_total = Counter(
            name="engagement_conductor_interventions_total",
            description="Total interventions executed",
            labels=("type", "outcome"),
        )

        self.intervention_latency = Histogram(
            name="engagement_conductor_intervention_latency_seconds",
            description="Latency of intervention execution",
            labels=("type",),
        )

        # Thompson Sampling Metrics
        self.thompson_sampling_selections = Counter(
            name="engagement_conductor_thompson_sampling_selections_total",
            description="Thompson Sampling intervention selections",
            labels=("intervention_type", "context"),
        )

        self.thompson_sampling_success_rate = Gauge(
            name="engagement_conductor_thompson_sampling_success_rate",
            description="Current success rate for intervention type in context",
            labels=("intervention_type", "context"),
        )

        # Anomaly Detection Metrics
        self.anomalies_detected = Counter(
            name="engagement_conductor_anomalies_detected_total",
            description="Total anomalies detected",
            labels=("type", "severity"),
        )

        # Circuit Breaker Metrics
        self.circuit_breaker_state = Gauge(
            name="engagement_conductor_circuit_breaker_state",
            description="Circuit breaker state (0=closed, 1=open, 2=half-open)",
            labels=("name",),
        )

        self.circuit_breaker_failures = Counter(
            name="engagement_conductor_circuit_breaker_failures_total",
            description="Circuit breaker failure count",
            labels=("name",),
        )

        # Rate Limiter Metrics
        self.rate_limit_rejections = Counter(
            name="engagement_conductor_rate_limit_rejections_total",
            description="Rate limiter rejections",
            labels=("limiter",),
        )

        # Worker Pool Metrics
        self.worker_pool_queue_depth = Gauge(
            name="engagement_conductor_worker_pool_queue_depth",
            description="Current queue depth for worker pool",
            labels=("worker_id",),
        )

        self.worker_pool_processed = Counter(
            name="engagement_conductor_worker_pool_processed_total",
            description="Events processed by worker pool",
            labels=("worker_id",),
        )

        # Session Metrics
        self.active_sessions = Gauge(
            name="engagement_conductor_active_sessions",
            description="Number of active sessions being monitored",
            labels=(),
        )

        self.pending_approvals = Gauge(
            name="engagement_conductor_pending_approvals",
            description="Number of pending intervention approvals",
            labels=(),
        )

        # Engagement Metrics
        self.engagement_score_current = Gauge(
            name="engagement_conductor_engagement_score_current",
            description="Current engagement score",
            labels=("session_id",),
        )

        # Error Metrics
        self.errors_total = Counter(
            name="engagement_conductor_errors_total",
            description="Total errors by type",
            labels=("component", "error_type"),
        )

        logger.info("Engagement Conductor metrics initialized")

    def export_metrics(self) -> Dict:
        """Export all metrics in a format suitable for /metrics endpoint."""
        return {
            "decisions": {
                "latency": self.decision_latency.get_stats(),
                "total": self.decisions_total.get_all(),
            },
            "interventions": {
                "total": self.interventions_total.get_all(),
                "latency": self.intervention_latency.get_stats(),
            },
            "thompson_sampling": {
                "selections": self.thompson_sampling_selections.get_all(),
            },
            "anomalies": {
                "detected": self.anomalies_detected.get_all(),
            },
            "circuit_breakers": {
                "state": self.circuit_breaker_state.get_all(),
                "failures": self.circuit_breaker_failures.get_all(),
            },
            "rate_limiter": {
                "rejections": self.rate_limit_rejections.get_all(),
            },
            "worker_pool": {
                "queue_depth": self.worker_pool_queue_depth.get_all(),
                "processed": self.worker_pool_processed.get_all(),
            },
            "sessions": {
                "active": self.active_sessions.get(),
                "pending_approvals": self.pending_approvals.get(),
            },
            "errors": {
                "total": self.errors_total.get_all(),
            },
        }

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        # Helper to format metric lines
        def add_metric(name: str, metric_type: str, description: str, values: Dict):
            lines.append(f"# HELP {name} {description}")
            lines.append(f"# TYPE {name} {metric_type}")
            for labels, value in values.items():
                if labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in zip(metric.label_names, labels))
                    lines.append(f"{name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")

        # Export counters
        for name, metric in [
            ("engagement_conductor_decisions_total", self.decisions_total),
            ("engagement_conductor_interventions_total", self.interventions_total),
            ("engagement_conductor_anomalies_detected_total", self.anomalies_detected),
            ("engagement_conductor_errors_total", self.errors_total),
        ]:
            add_metric(name, "counter", metric.description, metric.get_all())

        # Export gauges
        for name, metric in [
            ("engagement_conductor_active_sessions", self.active_sessions),
            ("engagement_conductor_pending_approvals", self.pending_approvals),
        ]:
            add_metric(name, "gauge", metric.description, metric.get_all())

        return "\n".join(lines)


# Global metrics instance
metrics = EngagementConductorMetrics()


def get_metrics() -> EngagementConductorMetrics:
    """Get the global metrics instance."""
    return metrics
