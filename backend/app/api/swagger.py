from __future__ import annotations
from copy import deepcopy
from typing import Any
from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
JSON_MEDIA = 'application/json'
MULTIPART_MEDIA = 'multipart/form-data'
FILE_FORM_FIELDS = {'file', 'map_file', 'actions_file', 'elevation_file'}

def _rewrite_refs(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_refs(element) for key, element in value.items()}
    if isinstance(value, list):
        return [_rewrite_refs(element) for element in value]
    if isinstance(value, str):
        return value.replace('#/components/schemas/', '#/definitions/')
    return value

def _schema_to_swagger2(value: Any) -> Any:
    if isinstance(value, list):
        return [_schema_to_swagger2(element) for element in value]
    if not isinstance(value, dict):
        if isinstance(value, str):
            return value.replace('#/components/schemas/', '#/definitions/')
        return value
    any_of = value.get('anyOf')
    if isinstance(any_of, list):
        concrete = [branche for branche in any_of if not (isinstance(branche, dict) and branche.get('type') == 'null')]
        has_null = len(concrete) != len(any_of)
        if has_null and len(concrete) == 1 and isinstance(concrete[0], dict):
            fusionne = {k: valeur_tmp for k, valeur_tmp in value.items() if k != 'anyOf'}
            fusionne.update(concrete[0])
            fusionne['x-nullable'] = True
            return _schema_to_swagger2(fusionne)
    converted: dict[str, Any] = {}
    for key, element in value.items():
        if key in {'$schema', '$id', 'unevaluatedProperties'}:
            continue
        if key == '$ref' and isinstance(element, str):
            converted[key] = element.replace('#/components/schemas/', '#/definitions/')
            continue
        if key == 'const':
            converted.setdefault('enum', [_schema_to_swagger2(element)])
            continue
        if key == 'nullable':
            converted['x-nullable'] = bool(element)
            continue
        if key == 'exclusiveMinimum' and isinstance(element, (int, float)) and (not isinstance(element, bool)):
            converted['minimum'] = element
            converted['exclusiveMinimum'] = True
            continue
        if key == 'exclusiveMaximum' and isinstance(element, (int, float)) and (not isinstance(element, bool)):
            converted['maximum'] = element
            converted['exclusiveMaximum'] = True
            continue
        if key == 'examples' and isinstance(element, list) and element:
            converted.setdefault('example', _schema_to_swagger2(element[0]))
            continue
        converted[key] = _schema_to_swagger2(element)
    return converted

def _resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get('$ref')
    prefix = '#/components/schemas/'
    if isinstance(ref, str) and ref.startswith(prefix):
        nom = ref[len(prefix):]
        resolved = components.get('schemas', {}).get(nom)
        if isinstance(resolved, dict):
            return resolved
    return schema

def _parameter_from_property(name: str, prop: dict[str, Any], *, required: bool) -> dict[str, Any]:
    parameter: dict[str, Any] = {'name': name, 'in': 'formData', 'required': required, 'description': prop.get('description', '')}
    if name in FILE_FORM_FIELDS or (prop.get('type') == 'string' and prop.get('format') == 'binary'):
        parameter['type'] = 'file'
        parameter['x-kakafandodo-file-input'] = True
        return parameter
    for key in ('type', 'format', 'default', 'enum', 'minimum', 'maximum', 'minLength', 'maxLength', 'pattern'):
        if key in prop:
            parameter[key] = _rewrite_refs(prop[key])
    if 'type' not in parameter and isinstance(prop.get('anyOf'), list):
        concrete = next((branche for branche in prop['anyOf'] if isinstance(branche, dict) and branche.get('type') != 'null'), None)
        if concrete:
            for key in ('type', 'format', 'enum', 'default'):
                if key in concrete:
                    parameter[key] = concrete[key]
    parameter.setdefault('type', 'string')
    return parameter

def openapi3_to_swagger2(openapi: dict[str, Any]) -> dict[str, Any]:
    source = deepcopy(openapi)
    composants = source.get('components', {})
    swagger: dict[str, Any] = {'swagger': '2.0', 'info': _rewrite_refs(source.get('info', {})), 'paths': {}, 'definitions': _schema_to_swagger2(composants.get('schemas', {})), 'produces': [JSON_MEDIA]}
    if source.get('tags'):
        swagger['tags'] = source['tags']
    if source.get('externalDocs'):
        swagger['externalDocs'] = source['externalDocs']
    security_schemes = composants.get('securitySchemes')
    if security_schemes:
        swagger['securityDefinitions'] = _rewrite_refs(security_schemes)
    for chemin, path_item in source.get('paths', {}).items():
        chemin_converti: dict[str, Any] = {}
        for method, operation in path_item.items():
            if method.lower() not in {'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}:
                continue
            op = deepcopy(operation)
            parameters = [_rewrite_refs(point) for point in op.pop('parameters', [])]
            request_body = op.pop('requestBody', None)
            if isinstance(request_body, dict):
                contenu = request_body.get('content', {})
                if MULTIPART_MEDIA in contenu:
                    media = contenu[MULTIPART_MEDIA]
                    schema = _resolve_schema(media.get('schema', {}), composants)
                    proprietes = schema.get('properties', {})
                    noms_requis = set(schema.get('required', []))
                    for nom, propriete in proprietes.items():
                        if not isinstance(propriete, dict):
                            propriete = {}
                        parameters.append(_parameter_from_property(nom, propriete, required=nom in noms_requis))
                    op['consumes'] = [MULTIPART_MEDIA]
                else:
                    media = contenu.get(JSON_MEDIA)
                    if media is None and contenu:
                        media = next(iter(contenu.values()))
                    if isinstance(media, dict):
                        parameters.append({'name': 'body', 'in': 'body', 'required': bool(request_body.get('required')), 'schema': _schema_to_swagger2(media.get('schema', {})), 'description': request_body.get('description', '')})
                        op['consumes'] = [JSON_MEDIA]
            if parameters:
                op['parameters'] = parameters
            responses: dict[str, Any] = {}
            for status, response in op.get('responses', {}).items():
                converted = {key: _rewrite_refs(value) for key, value in response.items() if key not in {'content', 'links'}}
                contenu = response.get('content', {})
                if isinstance(contenu, dict) and contenu:
                    if JSON_MEDIA in contenu:
                        media_type = JSON_MEDIA
                    elif 'text/plain' in contenu:
                        media_type = 'text/plain'
                    else:
                        media_type = next(iter(contenu))
                    media = contenu[media_type]
                    schema = media.get('schema')
                    if schema:
                        converted['schema'] = _schema_to_swagger2(schema)
                    example = media.get('example')
                    if example is not None:
                        converted.setdefault('examples', {})[media_type] = example
                    examples = media.get('examples')
                    if isinstance(examples, dict) and examples:
                        first = next(iter(examples.values()))
                        if isinstance(first, dict) and 'value' in first:
                            converted.setdefault('examples', {})[media_type] = first['value']
                responses[str(status)] = converted
            op['responses'] = responses
            chemin_converti[method] = _schema_to_swagger2(op)
        swagger['paths'][chemin] = chemin_converti
    return swagger

def install_custom_docs(app: FastAPI) -> None:

    @app.get('/swagger.json', include_in_schema=False)
    def swagger_schema() -> JSONResponse:
        return JSONResponse(openapi3_to_swagger2(app.openapi()))

    @app.get('/docs', include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url='/swagger.json', title=f'{app.title} - Swagger', swagger_ui_parameters={'deepLinking': True, 'displayRequestDuration': True, 'docExpansion': 'list', 'filter': True, 'persistAuthorization': True, 'tryItOutEnabled': True, 'defaultModelsExpandDepth': 2, 'defaultModelExpandDepth': 3})

    @app.get('/redoc', include_in_schema=False)
    def redoc() -> HTMLResponse:
        return get_redoc_html(openapi_url=app.openapi_url, title=f'{app.title} - ReDoc')
