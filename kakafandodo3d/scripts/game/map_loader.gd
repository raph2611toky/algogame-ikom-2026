class_name MapLoader
extends RefCounted

const ALLOWED_SYMBOLS := ".FM#toXG*+@"
const ELEVATION_HEADERS := ["ELEVATION", "HEIGHTS", "HEIGHT_MAP"]

static func load_from_file(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {
			"ok": false,
			"error": "Impossible d'ouvrir le fichier : %s" % path,
			"data": {}
		}
	var text: String = file.get_as_text()
	file.close()
	var result: Dictionary = parse_text(text, path)
	if not bool(result.get("ok", false)):
		return result

	# Format officiel de l'addendum : map.txt et elevation.txt sont séparés.
	# L'ancien format inline ELEVATION reste accepté pour compatibilité.
	var data: Dictionary = result.get("data", {})
	if not bool(data.get("has_explicit_elevation", false)):
		var elevation_path: String = path.get_base_dir().path_join("elevation.txt")
		if FileAccess.file_exists(elevation_path):
			var pair_result: Dictionary = ElevationLoader.load_pair(path, elevation_path)
			if not bool(pair_result.get("ok", false)):
				return pair_result
			var pair_data: Dictionary = pair_result.get("data", {})
			data["height_map"] = pair_data.get("height_map", [])
			data["has_explicit_elevation"] = true
			data["max_elevation"] = int(pair_data.get("max_elevation", 0))
			data["elevation_path"] = elevation_path
			result["data"] = data
	return result

static func parse_text(text: String, source_path: String = "") -> Dictionary:
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

	var terrain: Array = []
	var heroes: Dictionary = {}
	var machines: Array = []
	var chests: Array[Vector2i] = []
	var stones: Array[Vector2i] = []
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

	var height_map: Array = _zero_height_map(width, height)
	var has_explicit_elevation: bool = false
	var extra_start: int = height + 1
	if lines.size() > extra_start:
		var elevation_header: String = lines[extra_start].to_upper()
		if not ELEVATION_HEADERS.has(elevation_header):
			return _error("Après la grille, utilisez 'ELEVATION' suivi de %d lignes de hauteurs, ou retirez les lignes supplémentaires." % height)
		if lines.size() != extra_start + 1 + height:
			return _error("La section ELEVATION doit contenir exactement %d lignes." % height)
		var parsed_heights: Dictionary = _parse_height_rows(lines, extra_start + 1, width, height)
		if not bool(parsed_heights.get("ok", false)):
			return parsed_heights
		height_map = parsed_heights["data"]
		has_explicit_elevation = true

	var normalized_lines: Array[String] = ["%d %d %d" % [height, width, time_limit]]
	for row_index in range(height):
		normalized_lines.append(lines[row_index + 1])
	if has_explicit_elevation:
		normalized_lines.append("ELEVATION")
		for row_value in height_map:
			var values: Array[String] = []
			for level_value in row_value:
				values.append(str(int(level_value)))
			normalized_lines.append(" ".join(values))

	return {
		"ok": true,
		"error": "",
		"data": {
			"source_path": source_path,
			"height": height,
			"width": width,
			"time_limit": time_limit,
			"terrain": terrain,
			"heroes": heroes,
			"machines": machines,
			"chests": chests,
			"stones": stones,
			"terrain_counts": terrain_counts,
			"height_map": height_map,
			"has_explicit_elevation": has_explicit_elevation,
			"max_elevation": _max_height(height_map),
			"normalized_text": "\n".join(PackedStringArray(normalized_lines)),
		}
	}

static func _parse_height_rows(lines: Array[String], start_index: int, width: int, height: int) -> Dictionary:
	var result: Array = []
	for row_index in range(height):
		var raw: String = lines[start_index + row_index]
		var tokens: PackedStringArray = raw.split(" ", false)
		var row_values: Array[int] = []
		if tokens.size() == width:
			for token_value in tokens:
				var token: String = str(token_value)
				if not token.is_valid_int():
					return _error("Élévation ligne %d : '%s' n'est pas un entier." % [row_index + 1, token])
				var level: int = int(token)
				if level < 0 or level > 9:
					return _error("Élévation ligne %d : les niveaux doivent être compris entre 0 et 9." % [row_index + 1])
				row_values.append(level)
		elif raw.length() == width:
			for col_index in range(width):
				var digit: String = raw.substr(col_index, 1)
				if not digit.is_valid_int():
					return _error("Élévation ligne %d, colonne %d : '%s' n'est pas un chiffre." % [row_index + 1, col_index + 1, digit])
				row_values.append(int(digit))
		else:
			return _error("Élévation ligne %d : %d valeur(s), attendu %d." % [row_index + 1, tokens.size(), width])
		result.append(row_values)
	return {"ok": true, "error": "", "data": result}

static func _zero_height_map(width: int, height: int) -> Array:
	var result: Array = []
	for _row in range(height):
		var line: Array[int] = []
		for _col in range(width):
			line.append(0)
		result.append(line)
	return result

static func _max_height(height_map: Array) -> int:
	var maximum: int = 0
	for row_value in height_map:
		for level_value in row_value:
			maximum = maxi(maximum, int(level_value))
	return maximum

static func _error(message: String) -> Dictionary:
	return {"ok": false, "error": message, "data": {}}
