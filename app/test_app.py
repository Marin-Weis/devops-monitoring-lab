import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["ERROR_RATE"] = 0.0
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "healthy"}


def test_work_success_increments_metrics(client):
    assert client.get("/work").status_code == 200
    body = client.get("/metrics").get_data(as_text=True)
    assert 'app_jobs_processed_total{result="success"} 1.0' in body
    assert 'app_http_requests_total{endpoint="/work",method="GET",status="200"} 1.0' in body


def test_chaos_forces_errors(client):
    assert client.post("/chaos/1.0").status_code == 200
    assert client.get("/work").status_code == 500
    body = client.get("/metrics").get_data(as_text=True)
    assert 'app_jobs_processed_total{result="error"} 1.0' in body


def test_chaos_rejects_invalid_rate(client):
    assert client.post("/chaos/2.5").status_code == 400


def test_metrics_endpoint_not_counted(client):
    client.get("/metrics")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'endpoint="/metrics"' not in body
