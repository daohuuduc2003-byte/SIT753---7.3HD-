"""Smoke tests run against a deployed container (staging or production)."""
import json
import os
import urllib.request

import pytest

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8081").rstrip("/")
READ_ONLY = os.environ.get("SMOKE_READ_ONLY") == "1"


def fetch(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read()


def test_health_ok():
    status, body = fetch("/health")
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_home_page_loads():
    status, body = fetch("/")
    assert status == 200
    assert b"</html>" in body.lower()


def test_stylesheet_served():
    status, _ = fetch("/style.css")
    assert status == 200


def test_reviews_api_responds():
    status, body = fetch("/api/reviews")
    assert status == 200
    assert json.loads(body)["success"] is True


def test_metrics_exposed():
    status, body = fetch("/metrics")
    assert status == 200
    assert b"# TYPE" in body


@pytest.mark.skipif(READ_ONLY, reason="no writes against production")
def test_review_round_trip():
    status, body = fetch("/api/reviews", "POST", {
        "trail_name": "Smoke Test Trail", "reviewer": "Jenkins",
        "rating": 5, "comment": "Automated smoke test",
    })
    assert status == 201
    review_id = json.loads(body)["id"]
    status, _ = fetch(f"/api/reviews/{review_id}", "DELETE")
    assert status == 200
