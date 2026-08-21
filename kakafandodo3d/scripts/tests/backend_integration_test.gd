extends Node

func _ready() -> void:
	var health_response: Dictionary = await BackendAPI.health()
	assert(bool(health_response.get("ok", false)), str(health_response.get("error", "backend offline")))

	var strategies_response: Dictionary = await BackendAPI.get_strategies()
	assert(bool(strategies_response.get("ok", false)))
	var strategy_payload: Dictionary = strategies_response.get("data", {})
	assert(str(strategy_payload.get("default_strategy", "")) == "portfolio_v14")

	var map_file := FileAccess.open("res://data/maps/demo_simulation/map.txt", FileAccess.READ)
	assert(map_file != null)
	var map_text := map_file.get_as_text()
	map_file.close()

	var elevation_file := FileAccess.open("res://data/maps/demo_simulation/elevation.txt", FileAccess.READ)
	assert(elevation_file != null)
	var elevation_text := elevation_file.get_as_text()
	elevation_file.close()

	var parse_response: Dictionary = await BackendAPI.parse_map_text(map_text, "integration_3d", elevation_text)
	assert(bool(parse_response.get("ok", false)), str(parse_response.get("error", "parse failed")))
	var parsed: Dictionary = parse_response.get("data", {})
	assert(bool(parsed.get("has_elevation", false)))
	assert(parsed.get("elevation_rows", []).size() == int(parsed.get("height", 0)))

	var game_data := BackendStateAdapter.map_response_to_game_data(parsed, "res://data/maps/demo_simulation/map.txt", map_text)
	assert(bool(game_data.get("has_explicit_elevation", false)))
	assert(int(game_data.get("max_elevation", 0)) >= 1)
	assert(game_data.get("height_map", []).size() == int(parsed.get("height", 0)))

	var simulation_response: Dictionary = await BackendAPI.simulate(
		map_text,
		"integration_3d",
		{"name": "portfolio_v14"},
		elevation_text
	)
	assert(bool(simulation_response.get("ok", false)), str(simulation_response.get("error", "simulation failed")))
	var simulation: Dictionary = simulation_response.get("data", {})
	assert(simulation.has("ticks"))
	assert(simulation.has("actions_txt"))
	assert(bool(simulation.get("map", {}).get("has_elevation", false)))

	var state := StateSnapshotAdapter.create_state(simulation, simulation.get("initial_state", {}), "integration_3d")
	assert(state.has_explicit_elevation)
	assert(state.height_map.size() == state.height)

	var replay_response: Dictionary = await BackendAPI.replay_text(
		map_text,
		str(simulation.get("actions_txt", "")),
		"integration_3d_replay",
		elevation_text
	)
	assert(bool(replay_response.get("ok", false)))
	var replay: Dictionary = replay_response.get("data", {})
	assert(int(replay.get("result", {}).get("score", -1)) == int(simulation.get("result", {}).get("score", -2)))
	print("BACKEND_V14_3D_ELEVATION_OK score=", simulation.get("result", {}).get("score", 0), " ticks=", simulation.get("ticks", []).size())
	get_tree().quit()
