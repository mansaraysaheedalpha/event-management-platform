"""
Load Testing Configuration for Engagement Conductor AI

Uses Locust for simulating thousands of concurrent users/sessions.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8003

Or headless:
    locust -f tests/load/locustfile.py --host=http://localhost:8003 \
        --users 1000 --spawn-rate 50 --run-time 5m --headless

Scenarios tested:
1. Health check endpoints (high frequency)
2. Agent status polling
3. Intervention approval flow
4. Metrics collection
5. Simulated engagement events
"""

import json
import uuid
import random
from datetime import datetime, timezone
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


class EngagementConductorUser(HttpUser):
    """
    Simulates an event organizer interacting with the Engagement Conductor AI.

    Each user represents one active event session being monitored.
    """

    # Wait 1-3 seconds between tasks (simulates realistic user behavior)
    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user state when spawned."""
        self.session_id = str(uuid.uuid4())
        self.event_id = str(uuid.uuid4())
        self.auth_token = f"Bearer test_token_{self.session_id[:8]}"

        # Register session with agent
        self._register_session()

    def _register_session(self):
        """Register this user's session with the agent service."""
        response = self.client.post(
            "/api/v1/agent/sessions/register",
            json={
                "session_id": self.session_id,
                "event_id": self.event_id,
                "agent_mode": "SEMI_AUTO"
            },
            headers={"Authorization": self.auth_token},
            name="Register Session"
        )

    @task(10)
    def health_check(self):
        """High-frequency health check (10x weight)."""
        self.client.get("/health", name="Health Check")

    @task(5)
    def detailed_health(self):
        """Detailed health with component checks."""
        self.client.get("/health/detailed", name="Detailed Health")

    @task(20)
    def get_agent_status(self):
        """Poll agent status (most frequent operation)."""
        self.client.get(
            f"/api/v1/agent/sessions/{self.session_id}/status",
            headers={"Authorization": self.auth_token},
            name="Get Agent Status"
        )

    @task(3)
    def change_agent_mode(self):
        """Change agent mode (less frequent)."""
        modes = ["MANUAL", "SEMI_AUTO", "AUTO"]
        mode = random.choice(modes)

        self.client.put(
            f"/api/v1/agent/sessions/{self.session_id}/mode",
            json={"mode": mode},
            headers={"Authorization": self.auth_token},
            name="Change Agent Mode"
        )

    @task(5)
    def get_intervention_history(self):
        """Fetch intervention history for session."""
        self.client.get(
            f"/api/v1/interventions/history/{self.session_id}",
            headers={"Authorization": self.auth_token},
            name="Get Intervention History"
        )

    @task(2)
    def get_intervention_stats(self):
        """Fetch intervention statistics."""
        self.client.get(
            f"/api/v1/interventions/stats/{self.session_id}",
            headers={"Authorization": self.auth_token},
            name="Get Intervention Stats"
        )

    @task(1)
    def approve_decision(self):
        """Simulate approving a pending decision."""
        # First check if there's a pending decision
        response = self.client.get(
            f"/api/v1/agent/sessions/{self.session_id}/status",
            headers={"Authorization": self.auth_token},
            name="Check Pending Decision"
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "WAITING_APPROVAL":
                decision_id = data.get("current_decision", {}).get("id", self.session_id)
                self.client.post(
                    f"/api/v1/agent/sessions/{self.session_id}/decisions/{decision_id}/approve",
                    headers={"Authorization": self.auth_token},
                    name="Approve Decision"
                )

    @task(1)
    def get_metrics(self):
        """Fetch service metrics."""
        self.client.get("/metrics", name="Get Metrics")

    @task(1)
    def get_detailed_metrics(self):
        """Fetch detailed observability metrics."""
        self.client.get("/metrics/detailed", name="Get Detailed Metrics")


class EngagementEventSimulator(HttpUser):
    """
    Simulates engagement events from multiple concurrent sessions.

    This user type generates high-volume engagement signals to stress test
    the signal collector and anomaly detector.
    """

    wait_time = between(0.1, 0.5)  # High frequency

    def on_start(self):
        """Initialize simulator state."""
        self.sessions = [str(uuid.uuid4()) for _ in range(10)]  # Simulate 10 sessions per user
        self.event_ids = {s: str(uuid.uuid4()) for s in self.sessions}

    @task(10)
    def simulate_chat_message(self):
        """Simulate chat message event."""
        session_id = random.choice(self.sessions)
        event_id = self.event_ids[session_id]

        # This would normally be published to Redis
        # For HTTP load testing, we hit the health endpoint
        # In production, you'd use a Redis client to publish events
        self.client.get("/health/ping", name="Simulate Chat Event")

    @task(3)
    def simulate_poll_vote(self):
        """Simulate poll vote event."""
        self.client.get("/health/ping", name="Simulate Poll Vote")

    @task(1)
    def simulate_user_leave(self):
        """Simulate user leaving session."""
        self.client.get("/health/ping", name="Simulate User Leave")


class MetricsCollector(HttpUser):
    """
    Simulates a monitoring system scraping metrics.

    Runs at regular intervals to collect Prometheus metrics.
    """

    wait_time = between(10, 15)  # Every 10-15 seconds like Prometheus

    @task
    def scrape_prometheus_metrics(self):
        """Scrape Prometheus format metrics."""
        self.client.get("/metrics/prometheus", name="Prometheus Scrape")


# Event hooks for custom reporting
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests for investigation."""
    if response_time > 1000:  # > 1 second
        print(f"SLOW REQUEST: {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Setup before load test starts."""
    print("=" * 60)
    print("Starting Engagement Conductor AI Load Test")
    print("=" * 60)
    print(f"Target host: {environment.host}")
    if isinstance(environment.runner, MasterRunner):
        print(f"Running in distributed mode with {environment.runner.worker_count} workers")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup after load test ends."""
    print("=" * 60)
    print("Load Test Complete")
    print("=" * 60)


# Custom load shape for gradual ramp-up
class StagesShape:
    """
    Custom load shape with stages:
    1. Warmup: 10 users for 1 minute
    2. Ramp: 10 -> 100 users over 2 minutes
    3. Peak: 100 users for 3 minutes
    4. Spike: 200 users for 1 minute
    5. Recovery: Back to 100 users for 2 minutes
    6. Cool down: 100 -> 10 users over 1 minute
    """

    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 10},
        {"duration": 120, "users": 100, "spawn_rate": 1},
        {"duration": 180, "users": 100, "spawn_rate": 10},
        {"duration": 60, "users": 200, "spawn_rate": 10},
        {"duration": 120, "users": 100, "spawn_rate": 10},
        {"duration": 60, "users": 10, "spawn_rate": 10},
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            duration = stage["duration"]
            if run_time < duration:
                return (stage["users"], stage["spawn_rate"])
            run_time -= duration

        return None


# Configuration for different test scenarios
TEST_SCENARIOS = {
    "smoke": {
        "users": 10,
        "spawn_rate": 2,
        "run_time": "1m",
        "description": "Quick smoke test to verify basic functionality"
    },
    "load": {
        "users": 100,
        "spawn_rate": 10,
        "run_time": "5m",
        "description": "Normal load test with expected production traffic"
    },
    "stress": {
        "users": 500,
        "spawn_rate": 50,
        "run_time": "10m",
        "description": "Stress test to find breaking points"
    },
    "spike": {
        "users": 1000,
        "spawn_rate": 100,
        "run_time": "5m",
        "description": "Spike test simulating sudden traffic surge"
    },
    "soak": {
        "users": 200,
        "spawn_rate": 20,
        "run_time": "30m",
        "description": "Soak test for memory leaks and long-term stability"
    },
    "scale": {
        "users": 5000,
        "spawn_rate": 100,
        "run_time": "15m",
        "description": "Scale test for thousands of concurrent sessions"
    },
}


if __name__ == "__main__":
    print("Engagement Conductor AI Load Test Configuration")
    print("=" * 60)
    print("\nAvailable test scenarios:")
    for name, config in TEST_SCENARIOS.items():
        print(f"\n  {name}:")
        print(f"    Users: {config['users']}")
        print(f"    Spawn rate: {config['spawn_rate']}/s")
        print(f"    Duration: {config['run_time']}")
        print(f"    Description: {config['description']}")

    print("\n" + "=" * 60)
    print("Run with: locust -f tests/load/locustfile.py --host=http://localhost:8003")
