from __future__ import annotations
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.maps import MapParseResponse
from app.schemas.simulation import SimulationResponse
client = TestClient(app)

def test_custom_swagger_is_complete_and_uses_real_routes() -> None:
    response = client.get('/swagger.json')
    assert response.status_code == 200
    swagger = response.json()
    assert swagger['swagger'] == '2.0'
    expected_paths = {'/api/v1/health', '/api/v1/contracts', '/api/v1/maps/parse', '/api/v1/maps/upload', '/api/v1/settings', '/api/v1/settings/reset', '/api/v1/strategies', '/api/v1/simulation-jobs', '/api/v1/simulation-jobs/upload', '/api/v1/simulation-jobs/{job_id}', '/api/v1/simulation-jobs/{job_id}/result', '/api/v1/simulations', '/api/v1/simulations/upload', '/api/v1/simulations/replay', '/api/v1/simulations/replay-text', '/api/v1/simulations/replay-upload', '/api/v1/simulations/{simulation_id}', '/api/v1/simulations/{simulation_id}/actions.txt'}
    assert set(swagger['paths']) == expected_paths
    operation_ids: list[str] = []
    for path_item in swagger['paths'].values():
        for methode_http, operation in path_item.items():
            if methode_http not in {'get', 'post', 'put', 'patch', 'delete'}:
                continue
            assert 'summary' in operation
            assert 'responses' in operation
            operation_ids.append(operation['operationId'])
    assert len(operation_ids) == len(set(operation_ids))

def test_multipart_routes_are_manual_formdata_parameters_not_request_bodies() -> None:
    swagger = client.get('/swagger.json').json()
    expected = {'/api/v1/maps/upload': {'file': ('file', True), 'elevation_file': ('file', False)}, '/api/v1/simulations/upload': {'file': ('file', True), 'elevation_file': ('file', False), 'name': ('string', False), 'strategy_json': ('string', False)}, '/api/v1/simulations/replay-upload': {'map_file': ('file', True), 'actions_file': ('file', True), 'elevation_file': ('file', False), 'name': ('string', False), 'stop_when_objectives_finished': ('boolean', False)}, '/api/v1/simulation-jobs/upload': {'file': ('file', True), 'elevation_file': ('file', False), 'name': ('string', False), 'strategy_json': ('string', False)}}
    for chemin, fields in expected.items():
        operation = swagger['paths'][chemin]['post']
        assert 'requestBody' not in operation
        assert operation['consumes'] == ['multipart/form-data']
        parameters = {point['name']: point for point in operation['parameters']}
        assert set(parameters) == set(fields)
        for nom, (type_, required) in fields.items():
            assert parameters[nom]['in'] == 'formData'
            assert parameters[nom]['type'] == type_
            assert parameters[nom]['required'] is required
            if type_ == 'file':
                assert parameters[nom].get('x-kakafandodo-file-input') is True

def test_canonical_openapi_remains_fastapi_openapi3() -> None:
    openapi = client.get('/openapi.json').json()
    assert openapi['openapi'].startswith('3.')
    assert 'requestBody' in openapi['paths']['/api/v1/maps/upload']['post']
    assert 'requestBody' in openapi['paths']['/api/v1/simulations/upload']['post']
    assert 'requestBody' in openapi['paths']['/api/v1/simulation-jobs/upload']['post']

def test_docs_and_redoc_are_reachable() -> None:
    docs = client.get('/docs')
    redoc = client.get('/redoc')
    assert docs.status_code == 200
    assert redoc.status_code == 200
    assert '/swagger.json' in docs.text
    assert '/openapi.json' in redoc.text

def test_swagger_declared_models_match_actual_success_payloads() -> None:
    map_text = '3 5 60\nF.+.M\n.....\n..*@.\n'
    map_response = client.post('/api/v1/maps/parse', json={'name': 'swagger-check', 'map_text': map_text})
    assert map_response.status_code == 200
    MapParseResponse.model_validate(map_response.json())
    simulation = client.post('/api/v1/simulations', json={'mission': {'name': 'swagger-check', 'map_text': map_text}, 'strategy': {'name': 'portfolio_v3'}})
    assert simulation.status_code == 200
    SimulationResponse.model_validate(simulation.json())

def test_multipart_try_it_out_payloads_hit_the_real_views() -> None:
    map_text = b'3 5 60\nF.+.M\n.....\n..*@.\n'
    parsed = client.post('/api/v1/maps/upload', files={'file': ('mission.txt', map_text, 'text/plain')})
    assert parsed.status_code == 200
    assert parsed.json()['name'] == 'mission.txt'
    simulated = client.post('/api/v1/simulations/upload', files={'file': ('mission.txt', map_text, 'text/plain')}, data={'name': 'multipart', 'strategy_json': '{"name":"portfolio_v3"}'})
    assert simulated.status_code == 200
    payload = SimulationResponse.model_validate(simulated.json())
    replayed = client.post('/api/v1/simulations/replay-upload', files={'map_file': ('mission.txt', map_text, 'text/plain'), 'actions_file': ('actions.txt', payload.actions_txt.encode(), 'text/plain')}, data={'name': 'multipart-replay', 'stop_when_objectives_finished': 'false'})
    assert replayed.status_code == 200
    SimulationResponse.model_validate(replayed.json())
