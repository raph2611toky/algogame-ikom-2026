class_name DemoBrain
extends RefCounted

# Baseline fonctionnel pour démontrer la simulation.
# Il est volontairement séparé du moteur : l'équipe peut remplacer cette classe
# par son vrai solveur sans toucher au rendu, au parser ou aux règles du jeu.

func get_actions(state: GameState) -> Dictionary:
	return {
		"F": _choose_action(state, "F"),
		"M": _choose_action(state, "M"),
	}

func _choose_action(state: GameState, hero_id: String) -> String:
	var hero: Dictionary = state.heroes[hero_id]
	var hacking_machine := str(hero["hacking_machine"])

	if not hacking_machine.is_empty() and state.machines.has(hacking_machine):
		return _choose_hacking_action(state, hero_id, hacking_machine)

	var push_action: String = _maybe_push_chest(state, hero_id)
	if not push_action.is_empty():
		return push_action

	var stone_positions: Array = state.stones.keys()
	if not stone_positions.is_empty():
		var toward_stone: String = _first_action_to_targets(state, hero_id, stone_positions)
		if not toward_stone.is_empty():
			return toward_stone

	var compatible_machine_positions: Array = []
	for machine_id in state.machines:
		var machine: Dictionary = state.machines[machine_id]
		if (hero_id == "F" and machine["kind"] == "X") or (hero_id == "M" and machine["kind"] == "G"):
			compatible_machine_positions.append(machine["pos"])
	if not compatible_machine_positions.is_empty() and int(hero["battery"]) > 0:
		var same_machine: String = state.machine_at(Vector2i(hero["pos"]))
		if not same_machine.is_empty():
			var machine: Dictionary = state.machines[same_machine]
			if (hero_id == "F" and machine["kind"] == "X") or (hero_id == "M" and machine["kind"] == "G"):
				return "HACK"
		var toward_machine: String = _first_action_to_targets(state, hero_id, compatible_machine_positions)
		if not toward_machine.is_empty():
			return toward_machine

	return "WAIT"

func _choose_hacking_action(state: GameState, hero_id: String, machine_id: String) -> String:
	var machine: Dictionary = state.machines[machine_id]
	if bool(machine["pending_move"]):
		return "WAIT"

	if machine["kind"] == "G" and state.terrain_at(machine["pos"]) == "t":
		return "WAIT"

	var dir: Vector2i = ActionRules.orientation_to_vector(str(machine["orientation"]))
	var front: Vector2i = Vector2i(machine["pos"]) + dir

	if machine["kind"] == "X":
		if state.in_bounds(front) and state.terrain_at(front) == "o":
			return "HACK_FILL"
		var holes: Array = _terrain_positions(state, "o")
		if not holes.is_empty():
			var desired: String = _desired_orientation_toward(Vector2i(machine["pos"]), _nearest(Vector2i(machine["pos"]), holes))
			if desired != str(machine["orientation"]):
				return _rotation_toward(str(machine["orientation"]), desired)
		return "HACK_MOVE"

	var trees: Array = _terrain_positions(state, "t")
	if not trees.is_empty():
		var desired_tree: String = _desired_orientation_toward(Vector2i(machine["pos"]), _nearest(Vector2i(machine["pos"]), trees))
		if desired_tree != str(machine["orientation"]):
			return _rotation_toward(str(machine["orientation"]), desired_tree)
	return "HACK_MOVE"

func _maybe_push_chest(state: GameState, hero_id: String) -> String:
	var hero: Dictionary = state.heroes[hero_id]
	if int(hero["stamina"]) < 5:
		return ""
	var bushes: Array = _terrain_positions(state, "@")
	for action in ["UP", "DOWN", "LEFT", "RIGHT"]:
		var dir: Vector2i = ActionRules.DIRS[action]
		var chest_pos: Vector2i = Vector2i(hero["pos"]) + dir
		var chest_id: String = state.chest_at(chest_pos)
		if chest_id.is_empty():
			continue
		var dest: Vector2i = chest_pos + dir
		if not state.in_bounds(dest):
			continue
		var terrain: String = state.terrain_at(dest)
		if terrain == "#" or terrain == "t" or not state.chest_at(dest).is_empty() or not state.machine_at(dest).is_empty():
			continue
		if terrain == "o":
			continue
		if terrain == "@":
			return "PUSH_%s" % action
		if not bushes.is_empty():
			var before: int = _distance_to_nearest(chest_pos, bushes)
			var after: int = _distance_to_nearest(dest, bushes)
			if after < before:
				return "PUSH_%s" % action
	return ""

func _first_action_to_targets(state: GameState, hero_id: String, targets: Array) -> String:
	if targets.is_empty():
		return ""
	var start: Vector2i = state.heroes[hero_id]["pos"]
	if targets.has(start):
		return "WAIT"

	var queue: Array[Vector2i] = [start]
	var head: int = 0
	var visited: Dictionary = {start: true}
	var first_action: Dictionary = {start: ""}

	while head < queue.size():
		var pos: Vector2i = queue[head]
		head += 1
		for action in ["UP", "DOWN", "LEFT", "RIGHT"]:
			var next_value = _hero_destination(state, hero_id, pos, action)
			if next_value == null:
				continue
			var next_pos: Vector2i = next_value
			if visited.has(next_pos):
				continue
			visited[next_pos] = true
			first_action[next_pos] = action if pos == start else first_action[pos]
			if targets.has(next_pos):
				return str(first_action[next_pos])
			queue.append(next_pos)
	return ""

func _hero_destination(state: GameState, hero_id: String, pos: Vector2i, action: String):
	var dir: Vector2i = ActionRules.DIRS[action]
	var next: Vector2i = pos + dir
	if not state.in_bounds(next):
		return null
	var terrain: String = state.terrain_at(next)

	if hero_id == "F":
		if terrain == "#" or terrain == "t":
			return null
		if terrain == "o":
			var landing: Vector2i = next + dir
			if not state.in_bounds(landing):
				return null
			var landing_terrain: String = state.terrain_at(landing)
			if landing_terrain == "#" or landing_terrain == "t" or landing_terrain == "o":
				return null
			return landing
		return next

	if terrain == "#" or terrain == "o":
		return null
	if terrain == "t":
		var landing_m: Vector2i = next + dir
		if not state.in_bounds(landing_m):
			return null
		var landing_terrain_m: String = state.terrain_at(landing_m)
		if landing_terrain_m == "#" or landing_terrain_m == "o" or landing_terrain_m == "t":
			return null
		return landing_m
	return next

func _terrain_positions(state: GameState, symbol: String) -> Array:
	var out: Array = []
	for y in range(state.height):
		for x in range(state.width):
			var pos := Vector2i(x, y)
			if state.terrain_at(pos) == symbol:
				out.append(pos)
	return out

func _nearest(origin: Vector2i, positions: Array) -> Vector2i:
	var best: Vector2i = positions[0]
	var best_distance: int = origin.distance_squared_to(best)
	for pos in positions:
		var d: int = origin.distance_squared_to(Vector2i(pos))
		if d < best_distance:
			best = pos
			best_distance = d
	return best

func _distance_to_nearest(origin: Vector2i, positions: Array) -> int:
	if positions.is_empty():
		return 999999
	var best: int = 999999
	for pos in positions:
		best = mini(best, absi(origin.x - pos.x) + absi(origin.y - pos.y))
	return best

func _desired_orientation_toward(origin: Vector2i, target: Vector2i) -> String:
	var delta: Vector2i = target - origin
	if absi(delta.x) >= absi(delta.y):
		return "RIGHT" if delta.x >= 0 else "LEFT"
	return "DOWN" if delta.y >= 0 else "UP"

func _rotation_toward(current: String, desired: String) -> String:
	if ActionRules.rotate_cw(current) == desired:
		return "HACK_CW"
	if ActionRules.rotate_ccw(current) == desired:
		return "HACK_CCW"
	return "HACK_CW"
