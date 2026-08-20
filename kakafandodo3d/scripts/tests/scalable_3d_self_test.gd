extends Node

# Étape 1 : on valide uniquement le format de map et la structure d'élévation.
# Le renderer lui-même streame la zone visible et ne dépend pas du total de cases.
const CASES := {
	"res://data/maps/tests/scale_10_cells.txt": 10,
	"res://data/maps/tests/scale_100_cells.txt": 100,
	"res://data/maps/tests/scale_1000_cells.txt": 1000,
	"res://data/maps/tests/step1_streaming_80x120_9600_cells.txt": 9600,
}

func _ready() -> void:
	for path_value in CASES.keys():
		var path: String = str(path_value)
		var expected_cells: int = int(CASES[path])
		var parsed: Dictionary = MapLoader.load_from_file(path)
		assert(bool(parsed.get("ok", false)), "Map invalide: %s" % path)
		var data: Dictionary = parsed.get("data", {})
		var width: int = int(data.get("width", 0))
		var height: int = int(data.get("height", 0))
		assert(width * height == expected_cells)
		assert(bool(data.get("has_explicit_elevation", false)))
		var height_map: Array = data.get("height_map", [])
		assert(height_map.size() == height)
		for row_value in height_map:
			var row: Array = row_value
			assert(row.size() == width)
			for level_value in row:
				var level := int(level_value)
				assert(level >= 1 and level <= 9, "Elevation hors plage dans %s" % path)
		print("[STEP1 MAP TEST] %s : %d x %d = %d cases • Z1-9 OK" % [path.get_file(), width, height, expected_cells])

	var bridge_path := "res://data/maps/tests/step1_bridge_camera_18x18.txt"
	var bridge_parsed: Dictionary = MapLoader.load_from_file(bridge_path)
	assert(bool(bridge_parsed.get("ok", false)))
	var bridge_data: Dictionary = bridge_parsed.get("data", {})
	var bridge_heights: Array = bridge_data.get("height_map", [])
	var bridge_count: int = 0
	var bridge_h: int = int(bridge_data.get("height", 0))
	var bridge_w: int = int(bridge_data.get("width", 0))
	for y in range(bridge_h):
		for x in range(bridge_w):
			var current: int = int(bridge_heights[y][x])
			if x + 1 < bridge_w and absi(int(bridge_heights[y][x + 1]) - current) == 1:
				bridge_count += 1
			if y + 1 < bridge_h and absi(int(bridge_heights[y + 1][x]) - current) == 1:
				bridge_count += 1
	assert(bridge_count > 0)
	print("[STEP1 BRIDGE TEST] %d connexions ΔZ=1 détectées" % bridge_count)
	print("[STEP1] parser dynamique + Z1-9 + maps 10/100/1000/9600 : OK")
	get_tree().quit()
