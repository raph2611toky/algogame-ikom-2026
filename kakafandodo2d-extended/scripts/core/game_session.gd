class_name GameSessionService
extends Node

signal settings_changed
signal backend_status_changed(online: bool)

var selected_map_path: String = "res://data/maps/example_map.txt"
var selected_map_text: String = ""
var selected_elevation_path: String = ""
var selected_elevation_text: String = ""
var selected_map_data: Dictionary = {}
var selected_map_response: Dictionary = {}
var simulation: Dictionary = {}
var last_summary: Dictionary = {}
var last_actions_path: String = ""
var backend_online: bool = false
var available_strategies: Array[Dictionary] = []
var default_strategy_name: String = "portfolio_v14"

var settings: Dictionary = _default_settings()
var _sync_in_flight: bool = false
var _sync_pending: bool = false

func _ready() -> void:
	load_settings_local()
	apply_backend_endpoint()
	apply_settings()
	BackendAPI.connection_changed.connect(_on_backend_connection_changed)
	call_deferred("_initialize_backend")

func set_selected_map(
	path: String,
	data: Dictionary,
	map_text: String = "",
	backend_response: Dictionary = {},
	elevation_path: String = "",
	elevation_text: String = ""
) -> void:
	selected_map_path = path
	selected_map_data = data
	selected_map_text = map_text
	selected_map_response = backend_response
	selected_elevation_path = elevation_path
	selected_elevation_text = elevation_text
	simulation = {}
	last_summary = {}
	last_actions_path = ""

func set_simulation(value: Dictionary) -> void:
	simulation = value

func set_result(summary: Dictionary, actions_path: String) -> void:
	last_summary = summary
	last_actions_path = actions_path

func has_simulation() -> bool:
	return not simulation.is_empty() and simulation.has("ticks") and simulation.has("initial_state")

func get_strategy_options() -> Dictionary:
	var value: Variant = settings.get("strategy", {})
	if value is Dictionary and not value.is_empty():
		return value.duplicate(true)
	return _default_settings()["strategy"].duplicate(true)

func apply_backend_endpoint() -> void:
	# En build packagé, l'endpoint fourni par le launcher est prioritaire.
	# Il ne doit jamais être écrasé par user://settings.cfg.
	if BackendAPI.endpoint_forced:
		return
	BackendAPI.configure_endpoint(
		str(settings.get("backend_host", "127.0.0.1")),
		int(settings.get("backend_port", 8000))
	)


func is_packaged_mode() -> bool:
	return BackendAPI.packaged_mode


func runtime_backend_endpoint() -> Dictionary:
	return BackendAPI.runtime_endpoint()

func refresh_strategy_catalog() -> bool:
	apply_backend_endpoint()
	var response: Dictionary = await BackendAPI.get_strategies()
	if not bool(response.get("ok", false)):
		return false
	var payload: Dictionary = response.get("data", {})
	default_strategy_name = str(payload.get("default_strategy", "portfolio_v14"))
	available_strategies.clear()
	var raw: Variant = payload.get("strategies", [])
	if raw is Array:
		for item in raw:
			if item is Dictionary:
				available_strategies.append((item as Dictionary).duplicate(true))
	var available_names: Array[String] = []
	for item in available_strategies:
		available_names.append(str(item.get("name", "")))
	var options := get_strategy_options()
	if not available_names.has(str(options.get("name", ""))):
		options["name"] = default_strategy_name
		settings["strategy"] = options
	return true

func reset_settings() -> void:
	var current_host := str(settings.get("backend_host", "127.0.0.1"))
	var current_port := int(settings.get("backend_port", 8000))
	settings = _default_settings()
	# L'adresse backend est une configuration d'environnement, pas un réglage de jeu.
	settings["backend_host"] = current_host
	settings["backend_port"] = current_port
	apply_backend_endpoint()
	apply_settings()
	save_settings()

func reset_settings_remote() -> void:
	var response: Dictionary = await BackendAPI.reset_settings()
	if bool(response.get("ok", false)):
		var payload: Dictionary = response.get("data", {})
		var backend_settings: Variant = payload.get("settings", {})
		if backend_settings is Dictionary:
			_merge_settings(backend_settings)
			save_settings_local()
			apply_settings()
			return
	reset_settings()

func save_settings() -> void:
	save_settings_local()
	if _sync_in_flight:
		_sync_pending = true
		return
	call_deferred("_sync_settings_to_backend")


func persist_settings_now() -> Dictionary:
	apply_backend_endpoint()
	save_settings_local()
	while _sync_in_flight:
		await get_tree().process_frame
	_sync_in_flight = true
	_sync_pending = false
	var response: Dictionary = await BackendAPI.save_settings(_settings_payload())
	_sync_in_flight = false
	backend_online = bool(response.get("ok", false))
	backend_status_changed.emit(backend_online)
	if _sync_pending:
		_sync_pending = false
		call_deferred("_sync_settings_to_backend")
	return response

func preview_default_settings() -> void:
	var current_host := str(settings.get("backend_host", "127.0.0.1"))
	var current_port := int(settings.get("backend_port", 8000))
	settings = _default_settings()
	settings["backend_host"] = current_host
	settings["backend_port"] = current_port
	apply_backend_endpoint()
	apply_settings()

func replace_settings(value: Dictionary, apply_now: bool = true) -> void:
	settings = _default_settings()
	_merge_settings(value)
	apply_backend_endpoint()
	if apply_now:
		apply_settings()

func save_settings_local() -> void:
	var cfg := ConfigFile.new()
	for key in settings:
		if key == "strategy":
			cfg.set_value("strategy", "value", settings[key])
		else:
			cfg.set_value("settings", key, settings[key])
	cfg.save("user://settings.cfg")

func load_settings_local() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://settings.cfg") != OK:
		return
	for key in settings:
		if key == "strategy":
			settings[key] = cfg.get_value("strategy", "value", settings[key])
		else:
			settings[key] = cfg.get_value("settings", key, settings[key])

func refresh_settings_from_backend() -> bool:
	apply_backend_endpoint()
	var response: Dictionary = await BackendAPI.get_settings()
	if not bool(response.get("ok", false)):
		backend_online = false
		backend_status_changed.emit(false)
		return false
	var payload: Dictionary = response.get("data", {})
	var backend_settings: Variant = payload.get("settings", {})
	if backend_settings is Dictionary:
		_merge_settings(backend_settings)
		save_settings_local()
		apply_settings()
	backend_online = true
	backend_status_changed.emit(true)
	return true

func apply_settings() -> void:
	_ensure_audio_bus("Music")
	_ensure_audio_bus("Effects")
	_ensure_audio_bus("Dialogue")
	_set_bus_percent("Master", int(settings["sound"]))
	_set_bus_percent("Music", int(settings["music"]))
	_set_bus_percent("Effects", int(settings["effects"]))
	_set_bus_percent("Dialogue", int(settings["dialogue"]))
	var quality := int(settings["quality"])
	match quality:
		0: get_viewport().msaa_2d = Viewport.MSAA_DISABLED
		1: get_viewport().msaa_2d = Viewport.MSAA_2X
		2: get_viewport().msaa_2d = Viewport.MSAA_4X
		_: get_viewport().msaa_2d = Viewport.MSAA_8X
	var wanted_fullscreen := bool(settings["fullscreen"])
	var mode := DisplayServer.WINDOW_MODE_FULLSCREEN if wanted_fullscreen else DisplayServer.WINDOW_MODE_WINDOWED
	if DisplayServer.window_get_mode() != mode:
		DisplayServer.window_set_mode(mode)
	var locales := ["fr", "en", "mg"]
	var language_index := clampi(int(settings["language"]), 0, locales.size() - 1)
	TranslationServer.set_locale(locales[language_index])
	settings_changed.emit()

func save_actions_text(actions_text: String) -> String:
	var path := "user://actions.txt"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(actions_text)
	file.close()
	return ProjectSettings.globalize_path(path)

func _initialize_backend() -> void:
	apply_backend_endpoint()
	var health_response: Dictionary = await BackendAPI.health()
	backend_online = bool(health_response.get("ok", false))
	backend_status_changed.emit(backend_online)
	if backend_online:
		await refresh_strategy_catalog()
		await refresh_settings_from_backend()

func _sync_settings_to_backend() -> void:
	apply_backend_endpoint()
	if _sync_in_flight:
		_sync_pending = true
		return
	_sync_in_flight = true
	_sync_pending = false
	var response: Dictionary = await BackendAPI.save_settings(_settings_payload())
	_sync_in_flight = false
	backend_online = bool(response.get("ok", false))
	backend_status_changed.emit(backend_online)
	if _sync_pending:
		_sync_pending = false
		call_deferred("_sync_settings_to_backend")

func _settings_payload() -> Dictionary:
	return {
		"sound": int(settings.get("sound", 80)),
		"music": int(settings.get("music", 60)),
		"effects": int(settings.get("effects", 80)),
		"dialogue": int(settings.get("dialogue", 90)),
		"quality": int(settings.get("quality", 2)),
		"fullscreen": bool(settings.get("fullscreen", false)),
		"language": int(settings.get("language", 0)),
		"strategy": get_strategy_options(),
	}

func _merge_settings(backend_settings: Dictionary) -> void:
	# backend_host/backend_port sont volontairement LOCAUX au frontend.
	# Le backend distant ne doit jamais pouvoir remplacer son propre endpoint.
	for key in ["sound", "music", "effects", "dialogue", "quality", "fullscreen", "language", "strategy"]:
		if backend_settings.has(key):
			settings[key] = backend_settings[key]

func _on_backend_connection_changed(value: bool) -> void:
	backend_online = value
	backend_status_changed.emit(value)

func _ensure_audio_bus(name: String) -> void:
	if AudioServer.get_bus_index(name) != -1:
		return
	AudioServer.add_bus()
	AudioServer.set_bus_name(AudioServer.bus_count - 1, name)

func _set_bus_percent(name: String, percent: int) -> void:
	var index := AudioServer.get_bus_index(name)
	if index == -1:
		return
	var linear := clampf(float(percent) / 100.0, 0.0001, 1.0)
	AudioServer.set_bus_volume_db(index, linear_to_db(linear))

static func _default_settings() -> Dictionary:
	return {
		"sound": 80,
		"music": 60,
		"effects": 80,
		"dialogue": 90,
		"quality": 2,
		"fullscreen": false,
		"language": 0,
		"backend_host": "127.0.0.1",
		"backend_port": 8000,
		"strategy": {
			"name": "portfolio_v14",
			"max_stones_per_hero": 16,
			"max_chest_pairs_per_hero": 12,
			"max_unlock_obstacles": 20,
			"unlock_pair_candidates": 8,
			"stuck_end_threshold": 8,
			"scalable_max_ticks": 250,
		},
	}
