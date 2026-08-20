class_name GameState
extends RefCounted

var width: int = 0
var height: int = 0
var time_limit: int = 0
var remaining_time: int = 0
var tick: int = 0

# La grille terrain ne contient que . # t o @.
# Les héros, machines, coffres et pierres sont stockés séparément afin
# d'autoriser plusieurs catégories d'objets sur la même cellule.
var terrain: Array = []
# Données de relief synchronisées avec elevation.txt / backend V14.
# En mode historique sans elevation.txt, toutes les valeurs restent à 0.
var elevations: Array = []
var has_elevation: bool = false
var max_elevation: int = 0
var heroes: Dictionary = {}
var machines: Dictionary = {}
var chests: Dictionary = {}
var stones: Dictionary = {}
var bush_chests: Dictionary = {}

var hidden_chests: int = 0
var lost_chests: int = 0
var collected_stones: int = 0
var total_chests: int = 0
var total_stones: int = 0

var action_history: Array[String] = []
var ended: bool = false
var end_reason: String = ""
var source_path: String = ""

func setup(map_data: Dictionary) -> void:
	width = int(map_data["width"])
	height = int(map_data["height"])
	time_limit = int(map_data["time_limit"])
	remaining_time = time_limit
	terrain = map_data["terrain"].duplicate(true)
	elevations = map_data.get("elevations", []).duplicate(true)
	has_elevation = bool(map_data.get("has_elevation", false))
	max_elevation = int(map_data.get("max_elevation", _compute_max_elevation(elevations)))
	if elevations.is_empty():
		elevations = _zero_elevations(width, height)
		max_elevation = 0
	source_path = str(map_data.get("source_path", ""))

	heroes = {
		"F": _new_hero("F", Vector2i(map_data["heroes"]["F"])),
		"M": _new_hero("M", Vector2i(map_data["heroes"]["M"])),
	}

	machines.clear()
	var x_index: int = 0
	var g_index: int = 0
	for entry_value in map_data["machines"]:
		var entry: Dictionary = entry_value
		var kind: String = str(entry["kind"])
		var index: int = x_index if kind == "X" else g_index
		var machine_id: String = "%s%d" % [kind, index]
		if kind == "X":
			x_index += 1
		else:
			g_index += 1
		machines[machine_id] = _new_machine(machine_id, kind, Vector2i(entry["pos"]))

	chests.clear()
	var chest_index: int = 0
	for chest_pos_value in map_data["chests"]:
		var chest_pos: Vector2i = Vector2i(chest_pos_value)
		var chest_id: String = "C%d" % chest_index
		chests[chest_id] = {
			"id": chest_id,
			"pos": chest_pos,
		}
		chest_index += 1

	stones.clear()
	for stone_pos_value in map_data["stones"]:
		var stone_pos: Vector2i = Vector2i(stone_pos_value)
		stones[stone_pos] = int(stones.get(stone_pos, 0)) + 1

	bush_chests.clear()
	hidden_chests = 0
	lost_chests = 0
	collected_stones = 0
	total_chests = chests.size()
	total_stones = 0
	for count_value in stones.values():
		total_stones += int(count_value)

	action_history.clear()
	tick = 0
	ended = false
	end_reason = ""


static func _zero_elevations(map_width: int, map_height: int) -> Array:
	var result: Array = []
	for _row in range(map_height):
		var line: Array[int] = []
		for _col in range(map_width):
			line.append(0)
		result.append(line)
	return result

static func _compute_max_elevation(values: Array) -> int:
	var highest := 0
	for row_value in values:
		if not (row_value is Array):
			continue
		for value in row_value:
			highest = maxi(highest, int(value))
	return highest

func _new_hero(id: String, pos: Vector2i) -> Dictionary:
	return {
		"id": id,
		"pos": pos,
		"stamina": 100,
		"battery": 100,
		"rest_ticks": 0,
		"hacking_machine": "",
		"stones": 0,
		# Seulement pour le rendu 2D. Le GDD précise que F/M n'ont pas
		# d'état d'orientation de gameplay.
		"visual_facing": "DOWN",
		"last_action": "WAIT",
	}

func _new_machine(id: String, kind: String, pos: Vector2i) -> Dictionary:
	return {
		"id": id,
		"kind": kind,
		"pos": pos,
		# GDD : Excavator = LEFT, Grappler = RIGHT au départ.
		"orientation": "LEFT" if kind == "X" else "RIGHT",
		"hacked_by": "",
		# MOVE machine prend 2 ticks : queue puis exécution.
		"pending_move": false,
		"pending_source": "",
		"unhack_cooldown": 0,
		# Compteur de la routine automatique de l'excavateur.
		"steps_since_dig": 0,
		"stones": 0,
	}

func in_bounds(pos: Vector2i) -> bool:
	return pos.x >= 0 and pos.y >= 0 and pos.x < width and pos.y < height

func terrain_at(pos: Vector2i) -> String:
	if not in_bounds(pos):
		return "#"
	return str(terrain[pos.y][pos.x])

func elevation_at(pos: Vector2i) -> int:
	if not in_bounds(pos):
		return 0
	if pos.y < 0 or pos.y >= elevations.size():
		return 0
	var row_value: Variant = elevations[pos.y]
	if not (row_value is Array):
		return 0
	var row: Array = row_value
	if pos.x < 0 or pos.x >= row.size():
		return 0
	return int(row[pos.x])

func elevation_delta(start: Vector2i, destination: Vector2i) -> int:
	return elevation_at(destination) - elevation_at(start)

func set_terrain(pos: Vector2i, symbol: String) -> void:
	if in_bounds(pos):
		terrain[pos.y][pos.x] = symbol

func machine_at(pos: Vector2i) -> String:
	for machine_id_value in machines.keys():
		var machine_id: String = str(machine_id_value)
		var machine: Dictionary = machines[machine_id]
		if Vector2i(machine["pos"]) == pos:
			return machine_id
	return ""

func chest_at(pos: Vector2i) -> String:
	for chest_id_value in chests.keys():
		var chest_id: String = str(chest_id_value)
		var chest: Dictionary = chests[chest_id]
		if Vector2i(chest["pos"]) == pos:
			return chest_id
	return ""

func pickup_stones_by_hero(hero_id: String) -> int:
	var hero: Dictionary = heroes[hero_id]
	var pos: Vector2i = Vector2i(hero["pos"])
	var count: int = int(stones.get(pos, 0))
	if count > 0:
		stones.erase(pos)
		hero["stones"] = int(hero["stones"]) + count
		collected_stones += count
		heroes[hero_id] = hero
	return count

func pickup_stones_by_machine(machine_id: String) -> int:
	var machine: Dictionary = machines[machine_id]
	var pos: Vector2i = Vector2i(machine["pos"])
	var count: int = int(stones.get(pos, 0))
	if count > 0:
		stones.erase(pos)
		machine["stones"] = int(machine["stones"]) + count
		machines[machine_id] = machine
	return count

func steal_machine_stones(hero_id: String) -> int:
	var hero: Dictionary = heroes[hero_id]
	var machine_id: String = machine_at(Vector2i(hero["pos"]))
	if machine_id.is_empty():
		return 0
	var machine: Dictionary = machines[machine_id]
	var count: int = int(machine["stones"])
	if count <= 0:
		return 0
	machine["stones"] = 0
	hero["stones"] = int(hero["stones"]) + count
	collected_stones += count
	machines[machine_id] = machine
	heroes[hero_id] = hero
	return count

func remaining_machine_stones() -> int:
	var count: int = 0
	for machine_id_value in machines.keys():
		var machine_id: String = str(machine_id_value)
		count += int(machines[machine_id]["stones"])
	return count

func objectives_resolved() -> bool:
	return stones.is_empty() and remaining_machine_stones() == 0 and chests.is_empty()

func score() -> int:
	var stamina_total: int = int(heroes["F"]["stamina"]) + int(heroes["M"]["stamina"])
	var battery_total: int = int(heroes["F"]["battery"]) + int(heroes["M"]["battery"])
	var resource_bonus: int = int((stamina_total + battery_total) / 4)
	var time_bonus: int = int(remaining_time / 2)
	return (hidden_chests * 150) + (collected_stones * 25) + resource_bonus + time_bonus

func summary() -> Dictionary:
	var stamina_f: int = int(heroes["F"]["stamina"])
	var stamina_m: int = int(heroes["M"]["stamina"])
	var battery_f: int = int(heroes["F"]["battery"])
	var battery_m: int = int(heroes["M"]["battery"])
	var chest_points: int = hidden_chests * 150
	var stone_points: int = collected_stones * 25
	var resource_points: int = int((stamina_f + stamina_m + battery_f + battery_m) / 4)
	var time_points: int = int(remaining_time / 2)
	var completion_ratio: float = 0.0
	var objectives_total: int = total_chests + total_stones
	if objectives_total > 0:
		completion_ratio = float(hidden_chests + collected_stones) / float(objectives_total)
	return {
		"score": score(),
		"chest_points": chest_points,
		"stone_points": stone_points,
		"resource_points": resource_points,
		"time_points": time_points,
		"hidden_chests": hidden_chests,
		"lost_chests": lost_chests,
		"collected_stones": collected_stones,
		"total_chests": total_chests,
		"total_stones": total_stones,
		"stamina_f": stamina_f,
		"stamina_m": stamina_m,
		"battery_f": battery_f,
		"battery_m": battery_m,
		"remaining_time": remaining_time,
		"ticks": tick,
		"end_reason": end_reason,
		"source_path": source_path,
		"completion_ratio": completion_ratio,
		"actions_count": action_history.size(),
	}
