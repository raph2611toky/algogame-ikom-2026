from fastapi.testclient import TestClient

from app.main import app


MAP = """4 7 30
#######
#F+..K#
#M....#
#######"""


def test_health_and_contracts():
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200
    contract = client.get("/api/v1/contracts").json()
    assert contract["backend_authoritative"] is True
    assert len(contract["ai_profiles"]) == 3


def test_game_tick_is_idempotent():
    client = TestClient(app)
    created = client.post("/api/v1/games", json={"map_text": MAP, "difficulty": "hard"})
    assert created.status_code == 201
    game_id = created.json()["game_id"]
    payload = {
        "sequence": 1,
        "actions": {"F": {"action": "MOVE", "direction": "RIGHT"}, "M": {"action": "WAIT"}},
    }
    first = client.post(f"/api/v1/games/{game_id}/ticks", json=payload)
    duplicate = client.post(f"/api/v1/games/{game_id}/ticks", json=payload)
    assert first.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["version"] == first.json()["version"]


def test_sequence_gap_returns_conflict():
    client = TestClient(app)
    game_id = client.post("/api/v1/games", json={"map_text": MAP}).json()["game_id"]
    response = client.post(f"/api/v1/games/{game_id}/ticks", json={"sequence": 2})
    assert response.status_code == 409
