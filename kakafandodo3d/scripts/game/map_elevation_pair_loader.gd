class_name MapElevationPairLoader
extends RefCounted

# Charge le couple de fichiers officiel AlgoGames 2 :
#   - map.txt       : H W TIME puis H lignes ASCII
#   - elevation.txt : H lignes, W chiffres (0..9)
#
# Règle de l'addendum :
#   - cellules atteignables : altitude 1..9
#   - rochers (#)           : 0 (valeur non significative)

const ALLOWED_SYMBOLS := ".FM#toXG*+@"

static func load_pair(map_path: String, elevation_path: String) -> Dictionary:
	var map_result := _load_map(map_path)
	if not bool(map_result.get("ok", false)):
		return map_result
	var elevation_result := _load_elevation(elevation_path, map_result["data"])
	if not bool(elevation_result.get("ok", false)):
		return elevation_result

	var data: Dictionary = map_result["data"].duplicate(true)
	data["height_map"] = elevation_result["data"]
	data["elevation_path"] = elevation_path
	data["max_elevation"] = _max_height(elevation_result["data"])
	return {"ok": true, "error": "", "data": data}

static func _load_map(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _error("Impossible d'ouvrir map.txt : %s" % path)
	var text := file.get_as_text().replace("\r\n", "\n").replace("\r", "\n")
	file.close()

	var raw_lines := text.split("\n", false)
	var lines: Array[String] = []
	for raw in raw_lines:
		var line := str(raw).strip_edges()
		if not line.is_empty():
			lines.append(line)

	if lines.size() < 2:
		return _error("map.txt est vide ou incomplet.")
	var header: PackedStringArray = lines[0].split(" ", false)
	if header.size() != 3:
		return _error("La première ligne de map.txt doit être : H W TEMPS.")
	for token in header:
		if not str(token).is_valid_int():
			return _error("H, W et TEMPS doivent être des entiers.")

	var height := int(header[0])
	var width := int(header[1])
	var time_limit := int(header[2])
	if height <= 0 or width <= 0 or time_limit <= 0:
		return _error("H, W et TEMPS doivent être strictement positifs.")
	if lines.size() < height + 1:
		return _error("map.txt annonce %d lignes mais n'en contient pas assez." % height)

	var grid: Array[String] = []
	for row in range(height):
		var map_line: String = lines[row + 1]
		if map_line.length() != width:
			return _error("map.txt ligne %d : largeur %d au lieu de %d." % [row + 2, map_line.length(), width])
		for col in range(width):
			var symbol: String = map_line.substr(col, 1)
			if ALLOWED_SYMBOLS.find(symbol) == -1:
				return _error("Symbole '%s' invalide à (%d,%d)." % [symbol, row, col])
		grid.append(map_line)

	return {
		"ok": true,
		"error": "",
		"data": {
			"map_path": path,
			"height": height,
			"width": width,
			"time_limit": time_limit,
			"grid": grid,
		}
	}

static func _load_elevation(path: String, map_data: Dictionary) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _error("Impossible d'ouvrir elevation.txt : %s" % path)
	var text := file.get_as_text().replace("\r\n", "\n").replace("\r", "\n")
	file.close()

	var lines: Array[String] = []
	for raw in text.split("\n", false):
		var line := str(raw).strip_edges()
		if not line.is_empty():
			lines.append(line)

	var height := int(map_data["height"])
	var width := int(map_data["width"])
	var grid: Array[String] = []
	for grid_value in map_data.get("grid", []):
		grid.append(str(grid_value))
	if lines.size() != height:
		return _error("elevation.txt doit contenir exactement %d lignes (reçu : %d)." % [height, lines.size()])

	var result: Array = []
	for row in range(height):
		var raw: String = lines[row]
		var values: Array[int] = []
		var tokens: PackedStringArray = raw.split(" ", false)
		if tokens.size() == width:
			for token in tokens:
				if not str(token).is_valid_int():
					return _error("elevation.txt ligne %d : '%s' n'est pas un entier." % [row + 1, token])
				values.append(int(token))
		elif raw.length() == width:
			for col in range(width):
				var digit: String = raw.substr(col, 1)
				if not digit.is_valid_int():
					return _error("elevation.txt ligne %d colonne %d : valeur invalide." % [row + 1, col + 1])
				values.append(int(digit))
		else:
			return _error("elevation.txt ligne %d : largeur incorrecte (attendu %d valeurs)." % [row + 1, width])

		for col in range(width):
			var level: int = values[col]
			var symbol: String = grid[row].substr(col, 1)
			if symbol == "#":
				if level != 0:
					return _error("Le rocher en (%d,%d) doit avoir l'élévation 0." % [row, col])
			else:
				if level < 1 or level > 9:
					return _error("La cellule atteignable (%d,%d) doit avoir une élévation entre 1 et 9." % [row, col])
		result.append(values)

	return {"ok": true, "error": "", "data": result}

static func _max_height(height_map: Array) -> int:
	var maximum := 0
	for row in height_map:
		for value in row:
			maximum = maxi(maximum, int(value))
	return maximum

static func _error(message: String) -> Dictionary:
	return {"ok": false, "error": message, "data": {}}
