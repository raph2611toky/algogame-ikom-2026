class_name MapLoader
extends RefCounted

const ALLOWED_SYMBOLS := ".FM#toXG*+@"

static func load_from_file(path: String, elevation_path: String = "") -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {
			"ok": false,
			"error": "Impossible d'ouvrir le fichier : %s" % path,
			"data": {}
		}
	var text: String = file.get_as_text()
	file.close()

	var elevation_text := ""
	if not elevation_path.is_empty():
		var elevation_file := FileAccess.open(elevation_path, FileAccess.READ)
		if elevation_file == null:
			return _error("Impossible d'ouvrir elevation.txt : %s" % elevation_path)
		elevation_text = elevation_file.get_as_text()
		elevation_file.close()

	return parse_text(text, path, elevation_text)

static func parse_text(text: String, source_path: String = "", elevation_text: String = "") -> Dictionary:
	var normalized: String = text.replace("\r\n", "\n").replace("\r", "\n")
	if normalized.begins_with("\ufeff"):
		normalized = normalized.substr(1)

	var raw_lines: PackedStringArray = normalized.split("\n", false)
	var lines: Array[String] = []
	for raw_line_value in raw_lines:
		var line: String = str(raw_line_value).strip_edges()
		if line.is_empty():
			continue
		lines.append(line)

	if lines.size() < 2:
		return _error("Le fichier map est vide ou incomplet.")

	var header: PackedStringArray = lines[0].split(" ", false)
	if header.size() != 3:
		return _error("La première ligne doit contenir exactement : H W TEMPS.")

	if not str(header[0]).is_valid_int() or not str(header[1]).is_valid_int() or not str(header[2]).is_valid_int():
		return _error("H, W et TEMPS doivent être des entiers.")

	var height: int = int(header[0])
	var width: int = int(header[1])
	var time_limit: int = int(header[2])

	if height <= 0 or width <= 0 or time_limit <= 0:
		return _error("H, W et TEMPS doivent être strictement positifs.")
	if lines.size() < height + 1:
		return _error("Le fichier annonce %d lignes de carte, mais seulement %d sont présentes." % [height, lines.size() - 1])
	if lines.size() > height + 1:
		return _error("Le fichier contient %d ligne(s) de carte en trop." % (lines.size() - height - 1))

	var terrain: Array = []
	var heroes: Dictionary = {}
	var machines: Array = []
	var chests: Array[Vector2i] = []
	var stones: Array[Vector2i] = []
	var rocks: Dictionary = {}
	var count_f: int = 0
	var count_m: int = 0
	var terrain_counts: Dictionary = {"#": 0, "t": 0, "o": 0, "@": 0}

	for row_index in range(height):
		var row: String = lines[row_index + 1]
		if row.length() != width:
			return _error("Ligne %d : largeur %d au lieu de %d." % [row_index + 2, row.length(), width])

		var terrain_row: Array[String] = []
		for col_index in range(width):
			var symbol: String = row.substr(col_index, 1)
			if ALLOWED_SYMBOLS.find(symbol) == -1:
				return _error("Symbole '%s' invalide à la ligne %d, colonne %d." % [symbol, row_index + 2, col_index + 1])

			var pos: Vector2i = Vector2i(col_index, row_index)
			match symbol:
				"#", "t", "o", "@":
					terrain_row.append(symbol)
					terrain_counts[symbol] = int(terrain_counts.get(symbol, 0)) + 1
					if symbol == "#":
						rocks[pos] = true
				"F":
					terrain_row.append(".")
					heroes["F"] = pos
					count_f += 1
				"M":
					terrain_row.append(".")
					heroes["M"] = pos
					count_m += 1
				"X", "G":
					terrain_row.append(".")
					machines.append({"kind": symbol, "pos": pos})
				"*":
					terrain_row.append(".")
					chests.append(pos)
				"+":
					terrain_row.append(".")
					stones.append(pos)
				_:
					terrain_row.append(".")
		terrain.append(terrain_row)

	if count_f != 1 or count_m != 1:
		return _error("La carte doit contenir exactement un F (Ikotofosa) et un M (Imahaki).")

	var elevation_result := _parse_elevation(elevation_text, width, height, rocks)
	if not bool(elevation_result.get("ok", false)):
		return elevation_result
	var elevations: Array = elevation_result.get("elevations", [])
	var has_elevation := bool(elevation_result.get("has_elevation", false))
	var max_elevation := int(elevation_result.get("max_elevation", 0))

	var normalized_lines: Array[String] = ["%d %d %d" % [height, width, time_limit]]
	for row_index in range(height):
		normalized_lines.append(lines[row_index + 1])

	return {
		"ok": true,
		"error": "",
		"data": {
			"source_path": source_path,
			"height": height,
			"width": width,
			"time_limit": time_limit,
			"terrain": terrain,
			"elevations": elevations,
			"has_elevation": has_elevation,
			"max_elevation": max_elevation,
			"heroes": heroes,
			"machines": machines,
			"chests": chests,
			"stones": stones,
			"terrain_counts": terrain_counts,
			"normalized_text": "\n".join(PackedStringArray(normalized_lines)),
		}
	}

static func _parse_elevation(elevation_text: String, width: int, height: int, rocks: Dictionary) -> Dictionary:
	if elevation_text.strip_edges().is_empty():
		return {
			"ok": true,
			"error": "",
			"elevations": _zero_elevations(width, height),
			"has_elevation": false,
			"max_elevation": 0,
		}

	var normalized := elevation_text.replace("\r\n", "\n").replace("\r", "\n").strip_edges()
	if normalized.begins_with("\ufeff"):
		normalized = normalized.substr(1)
	var lines := normalized.split("\n", false)
	if lines.size() != height:
		return _error("elevation.txt : %d lignes attendues, %d reçues." % [height, lines.size()])

	var elevations: Array = []
	var max_elevation := 0
	for row_index in range(height):
		var row_text := str(lines[row_index]).strip_edges()
		if row_text.length() != width:
			return _error("elevation.txt ligne %d : largeur %d au lieu de %d." % [row_index + 1, row_text.length(), width])
		var row_values: Array[int] = []
		for col_index in range(width):
			var token := row_text.substr(col_index, 1)
			if not token.is_valid_int():
				return _error("elevation.txt doit contenir uniquement des chiffres 0..9.")
			var value := int(token)
			var pos := Vector2i(col_index, row_index)
			if rocks.has(pos):
				if value != 0:
					return _error("Le rocher en (%d,%d) doit avoir l'élévation 0." % [row_index, col_index])
			elif value == 0:
				return _error("La cellule accessible (%d,%d) doit avoir une élévation entre 1 et 9." % [row_index, col_index])
			row_values.append(value)
			max_elevation = maxi(max_elevation, value)
		elevations.append(row_values)
	return {
		"ok": true,
		"error": "",
		"elevations": elevations,
		"has_elevation": true,
		"max_elevation": max_elevation,
	}

static func _zero_elevations(width: int, height: int) -> Array:
	var elevations: Array = []
	for _row in range(height):
		var row_values: Array[int] = []
		for _col in range(width):
			row_values.append(0)
		elevations.append(row_values)
	return elevations

static func _error(message: String) -> Dictionary:
	return {"ok": false, "error": message, "data": {}}
