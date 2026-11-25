"""Small HTTP service instrumented for Prometheus.

Acts as the lab workload: exposes RED metrics (Rate, Errors, Duration),
an in-flight requests gauge, and a business job counter.
"""
import os
import random
import time

from flask import Flask, Response, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Simulated error rate on /work (0.0 -> 1.0), adjustable at runtime via POST /chaos/<rate>.
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.05"))


def create_app() -> Flask:
    app = Flask(__name__)
    registry = CollectorRegistry()

    requests_total = Counter(
        "app_http_requests_total",
        "Total number of HTTP requests",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "app_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["endpoint"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        registry=registry,
    )
    in_flight = Gauge(
        "app_http_requests_in_flight",
        "HTTP requests currently in flight",
        registry=registry,
    )
    jobs_total = Counter(
        "app_jobs_processed_total",
        "Business jobs processed by /work",
        ["result"],
        registry=registry,
    )
    app.config["ERROR_RATE"] = ERROR_RATE

    @app.before_request
    def _start_timer():
        g.start = time.perf_counter()
        in_flight.inc()

    @app.after_request
    def _record_metrics(response):
        # Exclude /metrics to avoid polluting application traffic stats.
        if request.path != "/metrics":
            endpoint = request.url_rule.rule if request.url_rule else "unmatched"
            elapsed = time.perf_counter() - g.start
            request_latency.labels(endpoint).observe(elapsed)
            requests_total.labels(request.method, endpoint, response.status_code).inc()
        in_flight.dec()
        return response

    @app.get("/")
    def index():
        return jsonify(service="devops-monitoring-lab", status="ok")

    @app.get("/health")
    def health():
        return jsonify(status="healthy")

    @app.get("/work")
    def work():
        """Simulate work with random latency and occasional HTTP 500 errors."""
        time.sleep(random.uniform(0.01, 0.25))
        if random.random() < app.config["ERROR_RATE"]:
            jobs_total.labels("error").inc()
            return jsonify(error="simulated failure"), 500
        jobs_total.labels("success").inc()
        return jsonify(result="job completed")

    @app.post("/chaos/<float:rate>")
    def chaos(rate: float):
        """Update the simulated error rate at runtime (useful to trigger alerts)."""
        if not 0.0 <= rate <= 1.0:
            return jsonify(error="rate must be between 0 and 1"), 400
        app.config["ERROR_RATE"] = rate
        return jsonify(error_rate=rate)

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
