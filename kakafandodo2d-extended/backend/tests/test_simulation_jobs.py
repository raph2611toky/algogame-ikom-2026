from time import sleep
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
MAP = '1 7 30\nF.+.M@*'


def test_simulation_job_returns_small_status_then_result() -> None:
    response = client.post('/api/v1/simulation-jobs', json={
        'mission': {'name': 'job-test', 'map_text': MAP},
        'strategy': {'name': 'heuristic_v1'},
    })
    assert response.status_code == 202
    job = response.json()
    assert job['status'] in {'queued', 'running', 'completed'}
    job_id = job['job_id']
    final = None
    for _ in range(100):
        status = client.get(f'/api/v1/simulation-jobs/{job_id}')
        assert status.status_code == 200
        final = status.json()
        if final['status'] in {'completed', 'failed'}:
            break
        sleep(0.01)
    assert final is not None
    assert final['status'] == 'completed', final
    result = client.get(f'/api/v1/simulation-jobs/{job_id}/result')
    assert result.status_code == 200
    payload = result.json()
    assert payload['job']['job_id'] == job_id
    assert payload['simulation']['mission_name'] == 'job-test'


def test_simulation_job_upload_is_real_file_parameter_in_swagger() -> None:
    swagger = client.get('/swagger.json').json()
    op = swagger['paths']['/api/v1/simulation-jobs/upload']['post']
    params = {item['name']: item for item in op['parameters']}
    assert params['file']['in'] == 'formData'
    assert params['file']['type'] == 'file'
