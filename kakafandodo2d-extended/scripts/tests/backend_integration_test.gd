extends Node

func _ready() -> void:
	var health_response: Dictionary = await BackendAPI.health()
	assert(bool(health_response.get("ok", false)))
	var settings_response: Dictionary = await BackendAPI.get_settings()
	assert(bool(settings_response.get("ok", false)))

	var file := FileAccess.open("res://data/maps/example_map.txt", FileAccess.READ)
	assert(file != null)
	var map_text := file.get_as_text()
	file.close()

	var elevation_file := FileAccess.open("res://data/maps/example_map_elevation.txt", FileAccess.READ)
	assert(elevation_file != null)
	var elevation_text := elevation_file.get_as_text()
	elevation_file.close()

	var parse_response: Dictionary = await BackendAPI.parse_map_text(map_text, "integration_test", elevation_text)
	assert(bool(parse_response.get("ok", false)))
	var parsed: Dictionary = parse_response.get("data", {})
	assert(bool(parsed.get("has_elevation", false)))
	assert(parsed.get("elevation_rows", []).size() == int(parsed.get("height", 0)))

	var simulation_response: Dictionary = await BackendAPI.simulate(
		map_text,
		"integration_test",
		GameSession.get_strategy_options(),
		elevation_text
	)
	assert(bool(simulation_response.get("ok", false)))
	var simulation: Dictionary = simulation_response.get("data", {})
	assert(simulation.has("ticks"))
	assert(simulation.has("actions_txt"))
	assert(bool(simulation.get("map", {}).get("has_elevation", false)))

	var replay_response: Dictionary = await BackendAPI.replay_text(
		map_text,
		str(simulation.get("actions_txt", "")),
		"integration_replay",
		elevation_text
	)
	assert(bool(replay_response.get("ok", false)))
	var replay: Dictionary = replay_response.get("data", {})
	assert(int(replay.get("result", {}).get("score", -1)) == int(simulation.get("result", {}).get("score", -2)))
	print("BACKEND_INTEGRATION_ELEVATION_OK score=", simulation.get("result", {}).get("score", 0), " ticks=", simulation.get("ticks", []).size())
	get_tree().quit()
