from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.settings_service import settings_service


client = TestClient(app)


def test_settings_get_put_reset(tmp_path: Path):
    original = settings_service._path
    settings_service._path = tmp_path / "settings.json"
    try:
        initial = client.get("/api/v1/settings")
        assert initial.status_code == 200
        assert initial.json()["settings"]["sound"] == 80
        payload = initial.json()["settings"]
        payload["sound"] = 37
        payload["strategy"]["name"] = "adaptive_v2"
        saved = client.put("/api/v1/settings", json=payload)
        assert saved.status_code == 200
        assert saved.json()["settings"]["sound"] == 37
        loaded = client.get("/api/v1/settings")
        assert loaded.json()["settings"]["strategy"]["name"] == "adaptive_v2"
        reset = client.post("/api/v1/settings/reset")
        assert reset.status_code == 200
        assert reset.json()["settings"]["sound"] == 80
        assert reset.json()["settings"]["strategy"]["name"] == "portfolio_v6"
    finally:
        settings_service._path = original
