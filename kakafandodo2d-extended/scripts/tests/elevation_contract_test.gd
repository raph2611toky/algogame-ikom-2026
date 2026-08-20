extends Node

func _ready() -> void:
	var result := MapLoader.load_from_file(
		"res://data/maps/tests/v14_complex_15x20.txt",
		"res://data/maps/tests/v14_complex_15x20_elevation.txt"
	)
	assert(bool(result.get("ok", false)), str(result.get("error", "")))
	var data: Dictionary = result.get("data", {})
	assert(bool(data.get("has_elevation", false)))
	assert(int(data.get("max_elevation", 0)) == 9)
	var state := GameState.new()
	state.setup(data)
	assert(state.elevation_at(Vector2i(0, 0)) == 6)
	assert(state.elevation_at(Vector2i(16, 0)) == 0) # rocher
	assert(state.elevation_at(Vector2i(8, 0)) == 8)
	print("ELEVATION_CONTRACT_OK max=", state.max_elevation)
	get_tree().quit()
