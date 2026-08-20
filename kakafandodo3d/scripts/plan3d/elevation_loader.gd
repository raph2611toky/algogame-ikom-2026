class_name ElevationLoader
extends RefCounted

const ALLOWED_SYMBOLS := ".FM#toXG*+@"

static func load_pair(map_path: String, elevation_path: String) -> Dictionary:
	var map_result: Dictionary = _load_map(map_path)
	if not bool(map_result.get("ok", false)):
		return map_result

	var elevation_result: Dictionary = _load_elevation(elevation_path, map_result["data"])
	if not bool(elevation_result.get("ok", false)):
		return elevation_result

	var data: Dictionary = map_result["data"].duplicate(true)
	data["height_map"] = elevation_result["data"]
	data["max_elevation"] = _max_height(elevation_result["data"])
	data["min_elevation"] = _min_height(elevation_result["data"])
	data["elevation_path"] = elevation_path
	return {"ok": true, "error": "", "data": data}

static func _load_map(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _error("Impossible d'ouvrir map.txt : %s" % path)

	var text: String = file.get_as_text().replace("\r\n", "\n").replace("\r", "\n")
	file.close()

	var lines: Array[String] = []
	for raw_line in text.split("\n", false):
		var line: String = str(raw_line).strip_edges()
		if not line.is_empty():
			lines.append(line)

	if lines.is_empty():
		return _error("map.txt est vide.")

	var header: PackedStringArray = lines[0].split(" ", false)
	if header.size() != 3:
		return _error("La première ligne de map.txt doit être : H W TEMPS.")

	for token in header:
		if not str(token).is_valid_int():
			return _error("H, W et TEMPS doivent être des entiers.")

	var rows: int = int(header[0])
	var cols: int = int(header[1])
	var time_limit: int = int(header[2])
	if rows <= 0 or cols <= 0 or time_limit <= 0:
		return _error("H, W et TEMPS doivent être strictement positifs.")
	if lines.size() < rows + 1:
		return _error("map.txt annonce %d lignes mais le fichier est incomplet." % rows)

	var grid: Array[String] = []
	for r in range(rows):
		var map_line: String = lines[r + 1]
		if map_line.length() != cols:
			return _error("map.txt ligne %d : largeur %d au lieu de %d." % [r + 2, map_line.length(), cols])
		for c in range(cols):
			var symbol: String = map_line.substr(c, 1)
			if ALLOWED_SYMBOLS.find(symbol) == -1:
				return _error("Symbole '%s' invalide à (%d,%d)." % [symbol, r, c])
		grid.append(map_line)

	return {
		"ok": true,
		"error": "",
		"data": {
			"map_path": path,
			"height": rows,
			"width": cols,
			"time_limit": time_limit,
			"grid": grid,
		}
	}

static func _load_elevation(path: String, map_data: Dictionary) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _error("Impossible d'ouvrir elevation.txt : %s" % path)

	var text: String = file.get_as_text().replace("\r\n", "\n").replace("\r", "\n")
	file.close()

	var lines: Array[String] = []
	for raw_line in text.split("\n", false):
		var line: String = str(raw_line).strip_edges()
		if not line.is_empty():
			lines.append(line)

	var rows: int = int(map_data["height"])
	var cols: int = int(map_data["width"])
	var grid: Array[String] = []
	for value in map_data["grid"]:
		grid.append(str(value))

	if lines.size() != rows:
		return _error("elevation.txt doit contenir exactement %d lignes (reçu : %d)." % [rows, lines.size()])

	var height_map: Array = []
	for r in range(rows):
		var raw: String = lines[r]
		var values: Array[int] = []
		var tokens: PackedStringArray = raw.split(" ", false)

		if tokens.size() == cols:
			for token in tokens:
				var token_text: String = str(token)
				if not token_text.is_valid_int():
					return _error("elevation.txt ligne %d : '%s' n'est pas un entier." % [r + 1, token_text])
				values.append(int(token_text))
		elif raw.length() == cols:
			for c in range(cols):
				var digit: String = raw.substr(c, 1)
				if not digit.is_valid_int():
					return _error("elevation.txt ligne %d colonne %d : valeur invalide." % [r + 1, c + 1])
				values.append(int(digit))
		else:
			return _error("elevation.txt ligne %d : %d valeurs attendues." % [r + 1, cols])

		for c in range(cols):
			var level: int = values[c]
			var symbol: String = grid[r].substr(c, 1)
			if symbol == "#":
				if level != 0:
					return _error("Le rocher en (%d,%d) doit avoir la valeur 0 dans elevation.txt." % [r, c])
			elif level < 1 or level > 9:
				return _error("La cellule (%d,%d) doit avoir une élévation entre 1 et 9." % [r, c])

		height_map.append(values)

	return {"ok": true, "error": "", "data": height_map}

static func _max_height(height_map: Array) -> int:
	var maximum: int = 1
	for row_value in height_map:
		var row: Array = row_value as Array
		for value in row:
			maximum = maxi(maximum, int(value))
	return maximum

static func _min_height(height_map: Array) -> int:
	var minimum: int = 9
	for row_value in height_map:
		var row: Array = row_value as Array
		for value in row:
			var level: int = int(value)
			if level > 0:
				minimum = mini(minimum, level)
	return minimum

static func _error(message: String) -> Dictionary:
	return {"ok": false, "error": message, "data": {}}
