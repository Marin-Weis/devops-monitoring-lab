"""Petit service HTTP instrumenté pour Prometheus.

Il sert de « charge de travail » au lab : on y expose des métriques RED
(Rate, Errors, Duration) + une jauge de requêtes en cours + un compteur métier.
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

# Taux d'erreurs simulées sur /work (0.0 → 1.0), réglable à chaud via l'API.
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.05"))


def create_app() -> Flask:
    app = Flask(__name__)
    registry = CollectorRegistry()

    requests_total = Counter(
        "app_http_requests_total",
        "Nombre total de requêtes HTTP",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "app_http_request_duration_seconds",
        "Latence des requêtes HTTP en secondes",
        ["endpoint"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        registry=registry,
    )
    in_flight = Gauge(
        "app_http_requests_in_flight",
        "Requêtes HTTP en cours de traitement",
        registry=registry,
    )
    jobs_total = Counter(
        "app_jobs_processed_total",
        "Jobs métier traités par /work",
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
        # On ignore /metrics pour ne pas polluer les statistiques applicatives.
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
        """Simule un traitement : latence aléatoire et erreurs 500 occasionnelles."""
        time.sleep(random.uniform(0.01, 0.25))
        if random.random() < app.config["ERROR_RATE"]:
            jobs_total.labels("error").inc()
            return jsonify(error="échec simulé"), 500
        jobs_total.labels("success").inc()
        return jsonify(result="job terminé")

    @app.post("/chaos/<float:rate>")
    def chaos(rate: float):
        """Change le taux d'erreurs à chaud (utile pour déclencher l'alerte)."""
        if not 0.0 <= rate <= 1.0:
            return jsonify(error="le taux doit être entre 0 et 1"), 400
        app.config["ERROR_RATE"] = rate
        return jsonify(error_rate=rate)

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
