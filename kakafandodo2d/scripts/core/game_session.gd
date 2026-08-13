class_name GameSessionService
extends Node

signal settings_changed

var selected_map_path: String = "res://data/maps/example_map.txt"
var selected_map_data: Dictionary = {}
var last_summary: Dictionary = {}
var last_actions_path: String = ""

var settings: Dictionary = {
	"sound": 80,
	"music": 60,
	"effects": 80,
	"dialogue": 90,
	"quality": 2,
	"fullscreen": false,
	"language": 0,
}

func _ready() -> void:
	load_settings()
	apply_settings()

func set_selected_map(path: String, data: Dictionary) -> void:
	selected_map_path = path
	selected_map_data = data

func set_result(summary: Dictionary, actions_path: String) -> void:
	last_summary = summary
	last_actions_path = actions_path

func reset_settings() -> void:
	settings = {
		"sound": 80,
		"music": 60,
		"effects": 80,
		"dialogue": 90,
		"quality": 2,
		"fullscreen": false,
		"language": 0,
	}
	apply_settings()
	save_settings()

func save_settings() -> void:
	var cfg := ConfigFile.new()
	for key in settings:
		cfg.set_value("settings", key, settings[key])
	cfg.save("user://settings.cfg")

func load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load("user://settings.cfg") != OK:
		return
	for key in settings:
		settings[key] = cfg.get_value("settings", key, settings[key])

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
