class_name LocalSimulationRunner
extends RefCounted

static func run(map_data: Dictionary, mission_name: String = "mission") -> Dictionary:
	var engine := SimulationEngine.new()
	var state: GameState = engine.initialize(map_data, DemoBrain.new())
	var initial_snapshot: Dictionary = _snapshot(state)
	var ticks: Array = []
	var action_lines: Array[String] = []
	var max_ticks: int = maxi(1, int(map_data.get("time_limit", 1)))

	while not state.ended and ticks.size() < max_ticks:
		var step_result: Dictionary = engine.step()
		var actions: Dictionary = step_result.get("actions", {"F": "WAIT", "M": "WAIT"})
		action_lines.append("%s | %s" % [str(actions.get("F", "WAIT")), str(actions.get("M", "WAIT"))])
		ticks.append({
			"index": state.tick,
			"effective_actions": actions.duplicate(true),
			"events": _copy_events(step_result.get("events", [])),
			"state": _snapshot(state),
		})

	if not state.ended:
		engine.finish_early("LIMITE_LOCALE")

	var rows: Array[String] = _rows_from_map_data(map_data)
	var result := {
		"score": state.score(),
		"chests_secured": state.hidden_chests,
		"chests_lost": state.lost_chests,
		"stones_collected": state.collected_stones,
		"remaining_time": state.remaining_time,
		"end_reason": state.end_reason,
	}
	return {
		"mode": "local",
		"mission_name": mission_name,
		"map": {
			"width": state.width,
			"height": state.height,
			"time_limit": state.time_limit,
			"rows": rows,
			"height_map": state.height_map.duplicate(true),
		},
		"height_map": state.height_map.duplicate(true),
		"has_explicit_elevation": state.has_explicit_elevation,
		"initial_state": initial_snapshot,
		"ticks": ticks,
		"result": result,
		"actions": action_lines.duplicate(),
		"actions_txt": "\n".join(PackedStringArray(action_lines)) + "\nEND_GAME\n",
	}

static func _snapshot(state: GameState) -> Dictionary:
	# Index spatial : sur une carte de 1000 cases, on ne rescane plus les
	# 1000 cellules à chaque tick pour reconstruire les props du replay.
	var rocks: Array = _position_dicts(state.terrain_positions("#"))
	var trees: Array = _position_dicts(state.terrain_positions("t"))
	var holes: Array = _position_dicts(state.terrain_positions("o"))
	var bushes: Array = _position_dicts(state.terrain_positions("@"))

	var stones: Array = []
	for pos_value in state.stones.keys():
		var stone_pos: Vector2i = Vector2i(pos_value)
		var count: int = int(state.stones.get(stone_pos, 0))
		for _index in range(count):
			stones.append(_pos_dict(stone_pos))

	var chests: Array = []
	for chest_id_value in state.chests.keys():
		var chest_id: String = str(chest_id_value)
		var chest: Dictionary = state.chests[chest_id]
		var chest_data: Dictionary = _pos_dict(Vector2i(chest["pos"]))
		chest_data["id"] = chest_id
		chests.append(chest_data)

	var heroes: Dictionary = {}
	for hero_id in ["F", "M"]:
		var hero: Dictionary = state.heroes[hero_id]
		heroes[hero_id] = {
			"position": _pos_dict(Vector2i(hero["pos"])),
			"stamina": int(hero["stamina"]),
			"battery": int(hero["battery"]),
			"hacking_machine_id": str(hero.get("hacking_machine", "")),
			"stones": int(hero.get("stones", 0)),
		}

	var machines: Dictionary = {}
	for machine_id_value in state.machines.keys():
		var machine_id: String = str(machine_id_value)
		var machine: Dictionary = state.machines[machine_id]
		machines[machine_id] = {
			"kind": str(machine["kind"]),
			"position": _pos_dict(Vector2i(machine["pos"])),
			"orientation": "FACING_%s" % str(machine["orientation"]),
			"hacked_by": str(machine.get("hacked_by", "")),
			"pending_move": bool(machine.get("pending_move", false)),
			"auto_move_pending": false,
			"steps_since_dig": int(machine.get("steps_since_dig", 0)),
			"carried_stones": int(machine.get("stones", 0)),
		}

	return {
		"elapsed": state.tick,
		"remaining_time": state.remaining_time,
		"ended": state.ended,
		"end_reason": state.end_reason,
		# height_map est statique pendant une simulation locale. Il reste stocké une seule
		# fois au niveau de simulation_data au lieu d'être dupliqué à chaque tick.
		# Cela évite une allocation O(cases × ticks), importante sur les cartes de 1000 cases.
		"props": {
			"rocks": rocks,
			"trees": trees,
			"holes": holes,
			"bushes": bushes,
			"stones": stones,
			"chests": chests,
			"secured_chests": state.hidden_chests,
			"lost_chests": state.lost_chests,
		},
		"score_inputs": {
			"hero_stones": state.collected_stones,
		},
		"heroes": heroes,
		"machines": machines,
	}

static func _position_dicts(positions: Array) -> Array:
	var result: Array = []
	result.resize(positions.size())
	for index in range(positions.size()):
		result[index] = _pos_dict(Vector2i(positions[index]))
	return result

static func _copy_events(events: Array) -> Array:
	var copied: Array = []
	for event_value in events:
		if event_value is Dictionary:
			var event: Dictionary = event_value
			copied.append(event.duplicate(true))
	return copied

static func _pos_dict(pos: Vector2i) -> Dictionary:
	return {"row": pos.y, "col": pos.x}

static func _rows_from_map_data(map_data: Dictionary) -> Array[String]:
	var width: int = int(map_data.get("width", 0))
	var height: int = int(map_data.get("height", 0))
	var rows: Array[String] = []
	var terrain: Array = map_data.get("terrain", [])
	for y in range(height):
		var chars: Array[String] = []
		for x in range(width):
			chars.append(str(terrain[y][x]))
		rows.append("".join(chars))
	var heroes: Dictionary = map_data.get("heroes", {})
	for hero_id in ["F", "M"]:
		var pos: Vector2i = Vector2i(heroes[hero_id])
		rows[pos.y] = _replace_char(rows[pos.y], pos.x, hero_id)
	for machine_value in map_data.get("machines", []):
		var machine: Dictionary = machine_value
		var pos: Vector2i = Vector2i(machine["pos"])
		rows[pos.y] = _replace_char(rows[pos.y], pos.x, str(machine["kind"]))
	for chest_value in map_data.get("chests", []):
		var pos: Vector2i = Vector2i(chest_value)
		rows[pos.y] = _replace_char(rows[pos.y], pos.x, "*")
	for stone_value in map_data.get("stones", []):
		var pos: Vector2i = Vector2i(stone_value)
		rows[pos.y] = _replace_char(rows[pos.y], pos.x, "+")
	return rows

static func _replace_char(text: String, index: int, value: String) -> String:
	if index < 0 or index >= text.length():
		return text
	return text.substr(0, index) + value + text.substr(index + 1)
