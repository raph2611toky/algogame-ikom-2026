class_name BackendStateAdapter
extends RefCounted

static func map_response_to_game_data(response: Dictionary, source_path: String, map_text: String) -> Dictionary:
	var width := int(response.get("width", 0))
	var height := int(response.get("height", 0))
	var rows: Array = response.get("rows", [])
	var terrain: Array = []
	var heroes: Dictionary = {}
	var machines: Array = []
	var chests: Array[Vector2i] = []
	var stones: Array[Vector2i] = []
	var terrain_counts := {"#": 0, "t": 0, "o": 0, "@": 0}
	for row_index in range(height):
		var row := str(rows[row_index])
		var terrain_row: Array[String] = []
		for col_index in range(width):
			var symbol := row.substr(col_index, 1)
			var pos := Vector2i(col_index, row_index)
			match symbol:
				"#", "t", "o", "@":
					terrain_row.append(symbol)
					terrain_counts[symbol] = int(terrain_counts.get(symbol, 0)) + 1
				"F", "M":
					terrain_row.append(".")
					heroes[symbol] = pos
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
	var elevation_rows: Array = response.get("elevation_rows", [])
	var elevations := _parse_elevation_rows(elevation_rows, width, height)
	var max_elevation := _max_elevation(elevations)
	return {
		"source_path": source_path,
		"height": height,
		"width": width,
		"time_limit": int(response.get("time_limit", 0)),
		"terrain": terrain,
		"elevations": elevations,
		"elevation_rows": elevation_rows.duplicate(true),
		"has_elevation": bool(response.get("has_elevation", false)),
		"max_elevation": max_elevation,
		"heroes": heroes,
		"machines": machines,
		"chests": chests,
		"stones": stones,
		"terrain_counts": terrain_counts,
		"normalized_text": _normalized_map_text(response, map_text),
	}

static func create_state(simulation: Dictionary, snapshot: Dictionary, source_path: String = "") -> GameState:
	var state := GameState.new()
	var map_data: Dictionary = simulation.get("map", {})
	state.width = int(map_data.get("width", 0))
	state.height = int(map_data.get("height", 0))
	state.time_limit = int(map_data.get("time_limit", 0))
	state.source_path = source_path
	state.has_elevation = bool(map_data.get("has_elevation", false))
	state.elevations = _parse_elevation_rows(
		map_data.get("elevation_rows", []),
		state.width,
		state.height
	)
	state.max_elevation = _max_elevation(state.elevations)
	state.total_chests = _initial_symbol_count(map_data.get("rows", []), "*")
	state.total_stones = _initial_symbol_count(map_data.get("rows", []), "+")
	apply_snapshot(state, snapshot, {})
	return state

static func apply_snapshot(state: GameState, snapshot: Dictionary, actions: Dictionary) -> void:
	state.tick = int(snapshot.get("elapsed", 0))
	state.remaining_time = int(snapshot.get("remaining_time", 0))
	state.ended = bool(snapshot.get("ended", false))
	state.end_reason = _text(snapshot.get("end_reason", ""))
	var props: Dictionary = snapshot.get("props", {})
	state.terrain = _empty_terrain(state.width, state.height)
	_fill_terrain(state, props.get("rocks", []), "#")
	_fill_terrain(state, props.get("trees", []), "t")
	_fill_terrain(state, props.get("holes", []), "o")
	_fill_terrain(state, props.get("bushes", []), "@")
	state.stones.clear()
	for item in props.get("stones", []):
		var pos := _pos(item)
		state.stones[pos] = int(state.stones.get(pos, 0)) + 1
	state.chests.clear()
	var chest_positions: Array[Vector2i] = []
	for item in props.get("chests", []):
		chest_positions.append(_pos(item))
	chest_positions.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return a.y < b.y or (a.y == b.y and a.x < b.x)
	)
	for index in range(chest_positions.size()):
		state.chests["C%d" % index] = {"id": "C%d" % index, "pos": chest_positions[index]}
	state.hidden_chests = int(props.get("secured_chests", 0))
	state.lost_chests = int(props.get("lost_chests", 0))
	var score_inputs: Dictionary = snapshot.get("score_inputs", {})
	state.collected_stones = int(score_inputs.get("hero_stones", 0))
	state.bush_chests.clear()
	var bushes: Array = props.get("bushes", [])
	if state.hidden_chests > 0 and not bushes.is_empty():
		state.bush_chests[_pos(bushes[0])] = state.hidden_chests
	var heroes_snapshot: Dictionary = snapshot.get("heroes", {})
	for hero_id in ["F", "M"]:
		var data: Dictionary = heroes_snapshot.get(hero_id, {})
		var previous: Dictionary = state.heroes.get(hero_id, {})
		var action := str(actions.get(hero_id, previous.get("last_action", "WAIT")))
		var facing := _visual_facing(action, str(previous.get("visual_facing", "DOWN")))
		state.heroes[hero_id] = {
			"id": hero_id,
			"pos": _pos(data.get("position", {})),
			"stamina": int(data.get("stamina", 100)),
			"battery": int(data.get("battery", 100)),
			"rest_ticks": 0,
			"hacking_machine": _text(data.get("hacking_machine_id", "")),
			"stones": int(data.get("stones", 0)),
			"visual_facing": facing,
			"last_action": action,
		}
	state.machines.clear()
	var machines_snapshot: Dictionary = snapshot.get("machines", {})
	for machine_id_value in machines_snapshot.keys():
		var machine_id := str(machine_id_value)
		var data: Dictionary = machines_snapshot[machine_id]
		state.machines[machine_id] = {
			"id": machine_id,
			"kind": str(data.get("kind", "X")),
			"pos": _pos(data.get("position", {})),
			"orientation": str(data.get("orientation", "FACING_LEFT")).trim_prefix("FACING_"),
			"hacked_by": _text(data.get("hacked_by", "")),
			"pending_move": bool(data.get("pending_move", false)) or bool(data.get("auto_move_pending", false)),
			"pending_source": "",
			"unhack_cooldown": 0,
			"steps_since_dig": int(data.get("steps_since_dig", 0)),
			"stones": int(data.get("carried_stones", 0)),
		}

static func events_to_frontend(events: Array) -> Array:
	var converted: Array = []
	for value in events:
		var event: Dictionary = value
		var data: Dictionary = event.get("data", {})
		var type_name := str(event.get("type", ""))
		var actor := _text(event.get("actor", ""))
		var position := _pos(event.get("position", {})) if event.get("position", null) != null else Vector2i(-1, -1)
		var result := {
			"type": _legacy_event_type(type_name),
			"id": _event_id(type_name, actor, data),
			"message": _text(event.get("message", "")),
		}
		if position.x >= 0:
			result["pos"] = position
			result["to"] = position
		if data.has("machine_id"):
			result["machine"] = str(data["machine_id"])
		if data.has("amount"):
			result["count"] = int(data["amount"])
		if data.has("reason"):
			result["reason"] = str(data["reason"])
		if type_name == "HERO_MOVED":
			var jumped := bool(data.get("jumped", false))
			result["style"] = "climb" if jumped and actor == "M" else ("hop" if jumped else "move")
		converted.append(result)
	return converted

static func result_to_summary(simulation: Dictionary, state: GameState) -> Dictionary:
	var result: Dictionary = simulation.get("result", {})
	var ticks: Array = simulation.get("ticks", [])
	var final_snapshot: Dictionary = simulation.get("initial_state", {})
	if not ticks.is_empty():
		var last_tick: Dictionary = ticks[ticks.size() - 1]
		final_snapshot = last_tick.get("state", {})
	var heroes: Dictionary = final_snapshot.get("heroes", {})
	var hero_f: Dictionary = heroes.get("F", {})
	var hero_m: Dictionary = heroes.get("M", {})
	var score := int(result.get("score", 0))
	var hidden := int(result.get("chests_secured", 0))
	var collected := int(result.get("stones_collected", 0))
	var stamina_f := int(hero_f.get("stamina", 0))
	var stamina_m := int(hero_m.get("stamina", 0))
	var battery_f := int(hero_f.get("battery", 0))
	var battery_m := int(hero_m.get("battery", 0))
	var remaining := int(result.get("remaining_time", 0))
	var total_objectives := state.total_chests + state.total_stones
	var completion := 0.0
	if total_objectives > 0:
		completion = float(hidden + collected) / float(total_objectives)
	return {
		"score": score,
		"chest_points": hidden * 150,
		"stone_points": collected * 25,
		"resource_points": int((stamina_f + stamina_m + battery_f + battery_m) / 4),
		"time_points": int(remaining / 2),
		"hidden_chests": hidden,
		"lost_chests": int(result.get("chests_lost", 0)),
		"collected_stones": collected,
		"total_chests": state.total_chests,
		"total_stones": state.total_stones,
		"stamina_f": stamina_f,
		"stamina_m": stamina_m,
		"battery_f": battery_f,
		"battery_m": battery_m,
		"remaining_time": remaining,
		"ticks": ticks.size(),
		"end_reason": _text(result.get("end_reason", "")),
		"source_path": state.source_path,
		"completion_ratio": completion,
		"actions_count": simulation.get("actions", []).size(),
	}

static func _text(value: Variant, fallback: String = "") -> String:
	if value == null:
		return fallback
	return str(value)

static func _empty_terrain(width: int, height: int) -> Array:
	var terrain: Array = []
	for _row in range(height):
		var line: Array[String] = []
		for _col in range(width):
			line.append(".")
		terrain.append(line)
	return terrain

static func _fill_terrain(state: GameState, positions: Array, symbol: String) -> void:
	for item in positions:
		var pos := _pos(item)
		if state.in_bounds(pos):
			state.terrain[pos.y][pos.x] = symbol

static func _pos(value: Variant) -> Vector2i:
	if value is Vector2i:
		return value
	if value is Dictionary:
		return Vector2i(int(value.get("col", 0)), int(value.get("row", 0)))
	return Vector2i.ZERO

static func _visual_facing(action: String, fallback: String) -> String:
	for direction in ["UP", "DOWN", "LEFT", "RIGHT"]:
		if action == direction or action == "PUSH_%s" % direction:
			return direction
	return fallback

static func _initial_symbol_count(rows: Array, symbol: String) -> int:
	var count := 0
	for row_value in rows:
		var row := str(row_value)
		for index in range(row.length()):
			if row.substr(index, 1) == symbol:
				count += 1
	return count

static func _parse_elevation_rows(rows: Array, width: int, height: int) -> Array:
	var parsed: Array = []
	for row_index in range(height):
		var line: Array[int] = []
		var row_text := str(rows[row_index]) if row_index < rows.size() else ""
		for col_index in range(width):
			var value := 0
			if col_index < row_text.length():
				var token := row_text.substr(col_index, 1)
				if token.is_valid_int():
					value = int(token)
			line.append(value)
		parsed.append(line)
	return parsed

static func _max_elevation(values: Array) -> int:
	var highest := 0
	for row_value in values:
		if row_value is Array:
			for value in row_value:
				highest = maxi(highest, int(value))
	return highest

static func _normalized_map_text(response: Dictionary, fallback: String) -> String:
	var rows: Array = response.get("rows", [])
	if rows.is_empty():
		return fallback
	var lines := PackedStringArray(["%d %d %d" % [int(response.get("height", 0)), int(response.get("width", 0)), int(response.get("time_limit", 0))]])
	for row in rows:
		lines.append(str(row))
	return "\n".join(lines)

static func _legacy_event_type(type_name: String) -> String:
	match type_name:
		"HERO_MOVED", "MACHINE_MOVED": return "move"
		"STONE_COLLECTED": return "stone_pickup"
		"STONES_STOLEN": return "stone_steal"
		"STONE_PICKED_BY_MACHINE": return "stone_pickup_machine"
		"CHEST_PUSHED": return "chest_move"
		"CHEST_SECURED": return "chest_hidden"
		"CHEST_LOST": return "chest_lost"
		"TREE_CUT": return "cut"
		"HOLE_FILLED": return "fill"
		"HOLE_DUG": return "dig"
		"MACHINE_HACKED": return "hack"
		"MACHINE_ROTATED": return "rotate"
		"MACHINE_MOVE_QUEUED", "HACK_MOVE_QUEUED": return "machine_move_queued"
		"MACHINE_MOVE_BLOCKED": return "machine_blocked"
		"STAMINA_RECOVERED": return "stamina_recover"
		"ACTION_COERCED_TO_WAIT": return "invalid_action"
		"UNHACK": return "unhack"
		_: return type_name.to_lower()

static func _event_id(type_name: String, actor: String, data: Dictionary) -> String:
	if type_name in ["MACHINE_ROTATED", "MACHINE_MOVE_QUEUED", "MACHINE_MOVE_BLOCKED", "MACHINE_MOVED"]:
		return _text(data.get("machine_id", actor), actor)
	if type_name == "HACK_MOVE_QUEUED":
		return _text(data.get("machine_id", actor), actor)
	return actor
