from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_strategy_catalog_exposes_latest_default() -> None:
    response = client.get('/api/v1/strategies')
    assert response.status_code == 200
    payload = response.json()
    assert payload['default_strategy'] == 'portfolio_v14'
    names = [item['name'] for item in payload['strategies']]
    assert names[0] == 'portfolio_v14'
    assert 'portfolio_v12' in names
    assert 'portfolio_v6' in names
    assert 'scalable_v1' in names
