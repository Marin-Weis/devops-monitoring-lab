#!/usr/bin/env python3
"""Génère le dashboard Grafana (JSON) du lab.

Le JSON produit est versionné dans ansible/roles/monitoring/files/dashboards/.
Garder le générateur permet de modifier les panneaux sans éditer un gros JSON à la main :
    python scripts/generate_dashboard.py
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
OUT = Path(__file__).resolve().parent.parent / "ansible/roles/monitoring/files/dashboards/app-overview.json"

_next_id = 0


def _id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


def target(expr: str, legend: str = "", ref: str = "A", instant: bool = False) -> dict:
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t["instant"] = True
        t["format"] = "table"
    return t


def stat(title, expr, x, w=6, unit="short", thresholds=None, decimals=None) -> dict:
    steps = thresholds or [{"color": "green", "value": None}]
    defaults = {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps}}
    if decimals is not None:
        defaults["decimals"] = decimals
    return {
        "id": _id(), "type": "stat", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": 0, "w": w, "h": 4},
        "targets": [target(expr)],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"colorMode": "background", "graphMode": "area", "reduceOptions": {"calcs": ["lastNotNull"]}},
    }


def timeseries(title, targets, x, y, w=12, h=8, unit="short") -> dict:
    return {
        "id": _id(), "type": "timeseries", "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"fillOpacity": 15, "lineWidth": 2}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
    }


panels = [
    stat("Requêtes / s", 'sum(rate(app_http_requests_total[1m]))', 0, unit="reqps", decimals=2),
    stat(
        "Taux d'erreurs 5xx",
        'sum(rate(app_http_requests_total{status=~"5.."}[1m])) / sum(rate(app_http_requests_total[1m]))',
        6, unit="percentunit", decimals=1,
        thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.05}, {"color": "red", "value": 0.10}],
    ),
    stat(
        "Latence p95",
        'histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))',
        12, unit="s", decimals=3,
        thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.3}, {"color": "red", "value": 0.5}],
    ),
    stat("Requêtes en cours", 'sum(app_http_requests_in_flight)', 18, decimals=0),
    timeseries(
        "Débit par code HTTP",
        [target('sum by (status) (rate(app_http_requests_total[1m]))', "{{status}}")],
        0, 4, unit="reqps",
    ),
    timeseries(
        "Latence (p50 / p95 / p99)",
        [
            target('histogram_quantile(0.50, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))', "p50", "A"),
            target('histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))', "p95", "B"),
            target('histogram_quantile(0.99, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))', "p99", "C"),
        ],
        12, 4, unit="s",
    ),
    timeseries(
        "Jobs traités par résultat",
        [target('sum by (result) (rate(app_jobs_processed_total[1m]))', "{{result}}")],
        0, 12, unit="ops",
    ),
    timeseries(
        "Disponibilité des cibles (up)",
        [target('up', "{{job}}")],
        12, 12,
    ),
    {
        "id": _id(), "type": "table", "title": "Alertes actives (firing / pending)", "datasource": DS,
        "gridPos": {"x": 0, "y": 20, "w": 24, "h": 6},
        "targets": [target('ALERTS{alertstate=~"firing|pending"}', instant=True)],
        "transformations": [{"id": "organize", "options": {"excludeByName": {"Time": True, "__name__": True, "Value": True}}}],
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {},
    },
]

dashboard = {
    "uid": "lab-app-overview",
    "title": "Lab DevOps — Vue d'ensemble de l'application",
    "tags": ["lab", "red-metrics"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "5s",
    "time": {"from": "now-15m", "to": "now"},
    "panels": panels,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Dashboard écrit : {OUT}")
