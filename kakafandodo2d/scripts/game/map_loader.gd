class_name MapLoader
extends RefCounted

const ALLOWED_SYMBOLS := ".FM#toXG*+@"

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
	return parse_text(text, path)

static func parse_text(text: String, source_path: String = "") -> Dictionary:
	var normalized: String = text.replace("\r\n", "\n").replace("\r", "\n")
	if normalized.begins_with("\ufeff"):
		normalized = normalized.substr(1)

	var raw_lines: PackedStringArray = normalized.split("\n", false)
	var lines: Array[String] = []
	for raw_line_value in raw_lines:
		var line: String = String(raw_line_value).strip_edges()
		if line.is_empty():
			continue
		lines.append(line)

	if lines.size() < 2:
		return _error("Le fichier map est vide ou incomplet.")

	var header: PackedStringArray = lines[0].split(" ", false)
	if header.size() != 3:
		return _error("La première ligne doit contenir exactement : H W TEMPS.")

	if not String(header[0]).is_valid_int() or not String(header[1]).is_valid_int() or not String(header[2]).is_valid_int():
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
			"heroes": heroes,
			"machines": machines,
			"chests": chests,
			"stones": stones,
			"terrain_counts": terrain_counts,
			"normalized_text": "\n".join(PackedStringArray(normalized_lines)),
		}
	}

static func _error(message: String) -> Dictionary:
	return {"ok": false, "error": message, "data": {}}
