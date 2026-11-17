from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FEED_1_1_1 = {"starter_g": 10, "flour_g": 10, "water_g": 10, "temp_c": 24}


@pytest.fixture
def client():
    return TestClient(create_app(seed=False))


def new_starter(client, name="Bubi"):
    return client.post("/api/starters", json={"name": name, "flour_type": "BL-80"}).json()["id"]


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Kovászdada" in r.text


def test_create_and_list_starter(client):
    r = client.post("/api/starters", json={"name": "  Bubi  ", "flour_type": "BL-80"})
    assert r.status_code == 201
    assert r.json()["name"] == "Bubi"
    assert r.json()["status"] is None
    assert [s["name"] for s in client.get("/api/starters").json()] == ["Bubi"]


def test_empty_name_rejected(client):
    assert client.post("/api/starters", json={"name": "   "}).status_code == 422


def test_feeding_and_status(client):
    sid = new_starter(client)
    r = client.post(f"/api/starters/{sid}/feedings", json=FEED_1_1_1)
    assert r.status_code == 201
    assert r.json()["peak_hours"] == 6.0
    assert r.json()["hydration_percent"] == 100.0

    st = client.get(f"/api/starters/{sid}/status").json()
    assert st["stage"] == "WAKING"


def test_status_of_hungry_starter(client):
    sid = new_starter(client)
    fed_at = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
    client.post(f"/api/starters/{sid}/feedings", json={**FEED_1_1_1, "fed_at": fed_at})
    assert client.get(f"/api/starters/{sid}/status").json()["stage"] == "HUNGRY"


def test_starter_details_include_feedings(client):
    sid = new_starter(client)
    client.post(f"/api/starters/{sid}/feedings", json=FEED_1_1_1)
    body = client.get(f"/api/starters/{sid}").json()
    assert body["feedings_count"] == 1
    assert len(body["feedings"]) == 1


def test_status_without_feeding_is_conflict(client):
    sid = new_starter(client)
    assert client.get(f"/api/starters/{sid}/status").status_code == 409


def test_unknown_starter_returns_404(client):
    assert client.get("/api/starters/999").status_code == 404
    assert client.post("/api/starters/999/feedings", json=FEED_1_1_1).status_code == 404


def test_invalid_temperature_rejected(client):
    sid = new_starter(client)
    r = client.post(f"/api/starters/{sid}/feedings", json={**FEED_1_1_1, "temp_c": 80})
    assert r.status_code == 422


def test_future_feeding_rejected(client):
    sid = new_starter(client)
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = client.post(f"/api/starters/{sid}/feedings", json={**FEED_1_1_1, "fed_at": future})
    assert r.status_code == 422


def test_plan_endpoint(client):
    target = datetime.now(timezone.utc) + timedelta(hours=24)
    r = client.post("/api/plan", json={**FEED_1_1_1, "target_at": target.isoformat()})
    assert r.status_code == 200
    feed_at = datetime.fromisoformat(r.json()["feed_at"])
    assert abs((target - timedelta(hours=6) - feed_at).total_seconds()) < 1
    assert r.json()["already_late"] is False


def test_suggest_ratio_endpoint(client):
    r = client.get("/api/suggest-ratio", params={"hours": 12, "temp_c": 24})
    assert r.status_code == 200
    assert r.json()["ratio"] == "1:4:4"


def test_suggest_ratio_validation(client):
    assert client.get("/api/suggest-ratio", params={"hours": 12, "temp_c": 99}).status_code == 422


def test_seeded_app_has_demo_starters():
    client = TestClient(create_app(seed=True))
    assert len(client.get("/api/starters").json()) == 2
