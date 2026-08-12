from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_map_route() -> None:
    response = client.post(
        "/api/v1/maps/parse",
        json={"name": "x", "map_text": "2 3 20\nF+.\nM.@\n"},
    )
    assert response.status_code == 200
    assert response.json()["counts"]["stones"] == 1


def test_simulate_route_returns_contract_and_actions() -> None:
    response = client.post(
        "/api/v1/simulations",
        json={
            "mission": {
                "name": "simple",
                "map_text": "3 5 30\nF.+@.\n..*..\nM....\n",
            }
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["contract_version"] == "1.0"
    assert payload["actions_txt"].endswith("END_GAME\n")
    assert "initial_state" in payload
    assert "ticks" in payload
    assert "result" in payload

    actions_url = payload["actions_download_url"]
    txt = client.get(actions_url)
    assert txt.status_code == 200
    assert txt.text.endswith("END_GAME\n")
