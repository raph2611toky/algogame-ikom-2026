class_name BackendAPIService
extends Node

signal connection_changed(online: bool)

const DEFAULT_BASE_URL := "http://127.0.0.1:8000/api/v1"
const REQUEST_TIMEOUT := 30.0
const SIMULATION_TIMEOUT := 120.0

var base_url: String = DEFAULT_BASE_URL
var online: bool = false
var last_error: String = ""

func health() -> Dictionary:
	var response := await _request_json("GET", "/health")
	_set_connection(bool(response.get("ok", false)))
	return response

func get_contracts() -> Dictionary:
	return await _request_json("GET", "/contracts")

func parse_map_text(map_text: String, mission_name: String = "mission") -> Dictionary:
	return await _request_json("POST", "/maps/parse", {
		"name": mission_name,
		"map_text": map_text,
	})

func parse_map_file(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _local_error("Impossible d'ouvrir le fichier : %s" % path)
	var bytes := file.get_buffer(file.get_length())
	file.close()
	return await _request_multipart_file("/maps/upload", "file", path.get_file(), bytes)

func simulate(map_text: String, mission_name: String, strategy: Dictionary = {}) -> Dictionary:
	var payload := {
		"mission": {
			"name": mission_name,
			"map_text": map_text,
		},
		"strategy": strategy if not strategy.is_empty() else _default_strategy(),
	}
	return await _request_json("POST", "/simulations", payload, SIMULATION_TIMEOUT)

func replay_text(map_text: String, actions_text: String, mission_name: String = "replay") -> Dictionary:
	return await _request_json("POST", "/simulations/replay-text", {
		"mission": {
			"name": mission_name,
			"map_text": map_text,
		},
		"actions_text": actions_text,
	})

func get_simulation(simulation_id: String) -> Dictionary:
	return await _request_json("GET", "/simulations/%s" % simulation_id.uri_encode())

func get_settings() -> Dictionary:
	return await _request_json("GET", "/settings")

func save_settings(settings_data: Dictionary) -> Dictionary:
	return await _request_json("PUT", "/settings", settings_data)

func reset_settings() -> Dictionary:
	return await _request_json("POST", "/settings/reset")

func test_connection() -> Dictionary:
	return await health()

func _request_json(method: String, endpoint: String, payload: Variant = null, timeout_seconds: float = REQUEST_TIMEOUT) -> Dictionary:
	var headers := PackedStringArray(["Accept: application/json"])
	var body := ""
	if payload != null:
		headers.append("Content-Type: application/json")
		body = JSON.stringify(payload)
	return await _perform_request(method, endpoint, headers, body, timeout_seconds)

func _request_multipart_file(endpoint: String, field_name: String, filename: String, file_bytes: PackedByteArray) -> Dictionary:
	var boundary := "----KakafandodoGodot%s" % str(Time.get_ticks_usec())
	var body := PackedByteArray()
	body.append_array(("--%s\r\n" % boundary).to_utf8_buffer())
	body.append_array(("Content-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n" % [field_name, filename]).to_utf8_buffer())
	body.append_array("Content-Type: text/plain; charset=utf-8\r\n\r\n".to_utf8_buffer())
	body.append_array(file_bytes)
	body.append_array(("\r\n--%s--\r\n" % boundary).to_utf8_buffer())
	var headers := PackedStringArray([
		"Accept: application/json",
		"Content-Type: multipart/form-data; boundary=%s" % boundary,
	])
	return await _perform_request_bytes("POST", endpoint, headers, body)

func _perform_request(method: String, endpoint: String, headers: PackedStringArray, body: String, timeout_seconds: float = REQUEST_TIMEOUT) -> Dictionary:
	var request := HTTPRequest.new()
	request.timeout = timeout_seconds
	add_child(request)
	var error := request.request(base_url + endpoint, headers, _method_value(method), body)
	if error != OK:
		request.queue_free()
		_set_connection(false)
		return _local_error("Erreur HTTPRequest : %s" % error_string(error))
	var response: Array = await request.request_completed
	request.queue_free()
	return _decode_response(response)

func _perform_request_bytes(method: String, endpoint: String, headers: PackedStringArray, body: PackedByteArray) -> Dictionary:
	var request := HTTPRequest.new()
	request.timeout = REQUEST_TIMEOUT
	add_child(request)
	var error := request.request_raw(base_url + endpoint, headers, _method_value(method), body)
	if error != OK:
		request.queue_free()
		_set_connection(false)
		return _local_error("Erreur HTTPRequest : %s" % error_string(error))
	var response: Array = await request.request_completed
	request.queue_free()
	return _decode_response(response)

func _decode_response(response: Array) -> Dictionary:
	if response.size() < 4:
		_set_connection(false)
		return _local_error("Réponse HTTP incomplète.")
	var result_code := int(response[0])
	var status_code := int(response[1])
	var body_bytes: PackedByteArray = response[3]
	var text := body_bytes.get_string_from_utf8()
	if result_code == HTTPRequest.RESULT_TIMEOUT:
		return _local_error("Le calcul de simulation a dépassé le délai HTTP. Le backend peut toujours être en train de calculer.", status_code, text)
	if result_code != HTTPRequest.RESULT_SUCCESS:
		_set_connection(false)
		return _local_error("Backend indisponible (résultat HTTP %d)." % result_code, status_code, text)
	var parsed: Variant = null
	if not text.is_empty():
		parsed = JSON.parse_string(text)
	if status_code < 200 or status_code >= 300:
		_set_connection(status_code > 0)
		var detail := text
		if parsed is Dictionary:
			detail = str(parsed.get("detail", text))
		return {
			"ok": false,
			"status": status_code,
			"error": detail,
			"data": parsed,
			"raw": text,
		}
	_set_connection(true)
	return {
		"ok": true,
		"status": status_code,
		"error": "",
		"data": parsed if parsed != null else {},
		"raw": text,
	}

func _set_connection(value: bool) -> void:
	if online == value:
		return
	online = value
	connection_changed.emit(online)

func _local_error(message: String, status: int = 0, raw: String = "") -> Dictionary:
	last_error = message
	return {
		"ok": false,
		"status": status,
		"error": message,
		"data": {},
		"raw": raw,
	}

func _method_value(method: String) -> HTTPClient.Method:
	match method.to_upper():
		"GET": return HTTPClient.METHOD_GET
		"POST": return HTTPClient.METHOD_POST
		"PUT": return HTTPClient.METHOD_PUT
		"PATCH": return HTTPClient.METHOD_PATCH
		"DELETE": return HTTPClient.METHOD_DELETE
		_: return HTTPClient.METHOD_GET

func _default_strategy() -> Dictionary:
	return {
		"name": "portfolio_v3",
		"max_stones_per_hero": 16,
		"max_chest_pairs_per_hero": 12,
		"max_unlock_obstacles": 20,
		"unlock_pair_candidates": 8,
		"stuck_end_threshold": 8,
		"scalable_max_ticks": 250,
	}
