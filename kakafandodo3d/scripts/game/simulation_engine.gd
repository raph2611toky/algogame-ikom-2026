class_name SimulationEngine
extends RefCounted

var state: GameState
# Intentionally Variant: any solver object exposing get_actions(state) can be plugged in.
var brain: Variant

func initialize(map_data: Dictionary, action_provider: Variant = null) -> GameState:
	state = GameState.new()
	state.setup(map_data)
	brain = action_provider if action_provider != null else DemoBrain.new()

	for hero_id in ["F", "M"]:
		var picked: int = state.pickup_stones_by_hero(hero_id)
		if picked > 0:
			pass
		state.steal_machine_stones(hero_id)
	return state

func step() -> Dictionary:
	if state == null or state.ended:
		return {
			"actions": {"F": "WAIT", "M": "WAIT"},
			"events": [],
			"ended": true,
			"score": 0 if state == null else state.score(),
		}

	state.tick += 1
	var events: Array = []

	# Snapshot début de tick : indispensable pour les machines voisines.
	var machine_positions_at_start: Dictionary = {}
	for start_machine_id_value in state.machines.keys():
		var start_machine_id: String = str(start_machine_id_value)
		var start_machine: Dictionary = state.machines[start_machine_id]
		var start_pos: Vector2i = Vector2i(start_machine["pos"])
		machine_positions_at_start[_pos_key(start_pos)] = start_machine_id

	var pending_at_start: Dictionary = {}
	for machine_id_value in state.machines.keys():
		var machine_id: String = str(machine_id_value)
		var machine: Dictionary = state.machines[machine_id]
		if bool(machine["pending_move"]):
			pending_at_start[machine_id] = str(machine["pending_source"])

	var requested: Dictionary = {"F": "WAIT", "M": "WAIT"}
	if brain != null and brain.has_method("get_actions"):
		var provider_result: Variant = brain.call("get_actions", state)
		if provider_result is Dictionary:
			requested = provider_result

	var actual: Dictionary = {"F": "WAIT", "M": "WAIT"}
	var hero_push_intents: Array = []

	for hero_id in ["F", "M"]:
		var action: String = _sanitize_action(str(requested.get(hero_id, "WAIT")))
		var hero: Dictionary = state.heroes[hero_id]
		var hacking_machine: String = str(hero["hacking_machine"])

		# Pendant le deuxième tick d'un HACK_MOVE, le héros WAIT automatiquement.
		if not hacking_machine.is_empty() and pending_at_start.has(hacking_machine):
			action = "WAIT"

		var prepared: Dictionary = _prepare_hero_action(hero_id, action, pending_at_start, events)
		actual[hero_id] = str(prepared.get("actual", "WAIT"))
		var push_value: Variant = prepared.get("push", null)
		if push_value is Dictionary:
			hero_push_intents.append(push_value)

	_process_hacked_grappler_waits(actual, pending_at_start, events)

	# Les mouvements machines arrivés à leur deuxième tick sont résolus ensemble.
	var machine_intents: Dictionary = _build_machine_move_intents(pending_at_start)
	var resolution: Dictionary = _plan_simultaneous_machines_and_chests(machine_intents, hero_push_intents)
	var push_plan: Dictionary = resolution["push_plan"]
	var machine_valid: Dictionary = resolution["machine_valid"]

	_apply_chest_plan(push_plan, events)

	# Déduire la stamina d'un PUSH seulement si le push a réellement réussi.
	var actor_success: Dictionary = push_plan.get("actor_success", {})
	for intent_value in hero_push_intents:
		var intent: Dictionary = intent_value
		var hero_id: String = str(intent["actor_id"])
		var actor_key: String = "hero:%s" % hero_id
		if bool(actor_success.get(actor_key, false)):
			var hero: Dictionary = state.heroes[hero_id]
			hero["stamina"] = maxi(0, int(hero["stamina"]) - 5)
			hero["rest_ticks"] = 0
			state.heroes[hero_id] = hero
		else:
			actual[hero_id] = "WAIT"
			events.append({"type": "invalid_action", "id": hero_id, "requested": str(requested.get(hero_id, "WAIT")), "reason": "push_blocked"})

	var moved_machines: Dictionary = _execute_machine_moves(machine_intents, machine_valid, events)
	_process_automatic_machines(pending_at_start, moved_machines, machine_positions_at_start, events)

	for hero_id in ["F", "M"]:
		var hero: Dictionary = state.heroes[hero_id]
		hero["last_action"] = str(actual[hero_id])
		state.heroes[hero_id] = hero

		_apply_rest_recovery(hero_id, str(actual[hero_id]), events)

		var picked: int = state.pickup_stones_by_hero(hero_id)
		if picked > 0:
			events.append({"type": "stone_pickup", "id": hero_id, "count": picked})

		var stolen: int = state.steal_machine_stones(hero_id)
		if stolen > 0:
			events.append({"type": "stone_steal", "id": hero_id, "count": stolen})

	state.remaining_time = maxi(0, state.remaining_time - 1)
	state.action_history.append("%s | %s" % [actual["F"], actual["M"]])

	if state.objectives_resolved():
		state.ended = true
		state.end_reason = "OBJECTIFS_TERMINES"
	elif state.remaining_time <= 0 or state.tick >= state.time_limit:
		state.ended = true
		state.end_reason = "TEMPS_ECOULE"

	return {
		"actions": actual,
		"events": events,
		"ended": state.ended,
		"score": state.score(),
	}

func finish_early(reason: String = "END_GAME") -> void:
	if state == null or state.ended:
		return
	state.ended = true
	state.end_reason = reason

func _sanitize_action(action: String) -> String:
	var upper: String = action.strip_edges().to_upper()
	return upper if ActionRules.HERO_ACTIONS.has(upper) else "WAIT"

func _prepare_hero_action(hero_id: String, action: String, pending_at_start: Dictionary, events: Array) -> Dictionary:
	var hero: Dictionary = state.heroes[hero_id]
	var hacking_machine: String = str(hero["hacking_machine"])

	# Si le dernier point de batterie a servi à HACK_MOVE, on garde le rider
	# jusqu'à l'exécution du MOVE au tick suivant.
	if (
		not hacking_machine.is_empty()
		and int(hero["battery"]) <= 0
		and state.machines.has(hacking_machine)
		and not pending_at_start.has(hacking_machine)
	):
		_unhack(hero_id, hacking_machine, "battery_empty", events)
		hero = state.heroes[hero_id]
		hacking_machine = ""

	if ActionRules.DIRS.has(action):
		var transition: Dictionary = _hero_transition(hero_id, Vector2i(hero["pos"]), action)
		if not bool(transition.get("ok", false)):
			events.append({"type": "invalid_action", "id": hero_id, "requested": action, "reason": "blocked"})
			return {"actual": "WAIT", "push": null}

		var cost: int = int(transition["cost"])
		if int(hero["stamina"]) < cost:
			events.append({"type": "invalid_action", "id": hero_id, "requested": action, "reason": "stamina"})
			return {"actual": "WAIT", "push": null}

		var from: Vector2i = Vector2i(hero["pos"])
		var to: Vector2i = Vector2i(transition["to"])
		hero["pos"] = to
		hero["stamina"] = int(hero["stamina"]) - cost
		hero["rest_ticks"] = 0
		hero["visual_facing"] = action
		state.heroes[hero_id] = hero
		events.append({"type": "move", "id": hero_id, "from": from, "to": to, "style": str(transition["style"])})

		if not hacking_machine.is_empty() and state.machines.has(hacking_machine):
			_unhack(hero_id, hacking_machine, "left_machine", events)
		return {"actual": action, "push": null}

	if action.begins_with("PUSH_"):
		if not hacking_machine.is_empty() or int(hero["stamina"]) < 5:
			return {"actual": "WAIT", "push": null}
		var dir: Vector2i = ActionRules.dir_for_action(action)
		var chest_pos: Vector2i = Vector2i(hero["pos"]) + dir
		var chest_id: String = state.chest_at(chest_pos)
		if chest_id.is_empty():
			events.append({"type": "invalid_action", "id": hero_id, "requested": action, "reason": "no_chest"})
			return {"actual": "WAIT", "push": null}
		return {
			"actual": action,
			"push": {
				"actor_key": "hero:%s" % hero_id,
				"actor_type": "hero",
				"actor_id": hero_id,
				"chest_id": chest_id,
				"dir": dir,
			}
		}

	if action == "HACK":
		if not hacking_machine.is_empty() or int(hero["battery"]) <= 0:
			return {"actual": "WAIT", "push": null}

		var machine_id: String = state.machine_at(Vector2i(hero["pos"]))
		if machine_id.is_empty():
			events.append({"type": "invalid_action", "id": hero_id, "requested": action, "reason": "no_machine"})
			return {"actual": "WAIT", "push": null}

		var machine: Dictionary = state.machines[machine_id]
		var compatible: bool = (
			(hero_id == "F" and str(machine["kind"]) == "X")
			or (hero_id == "M" and str(machine["kind"]) == "G")
		)
		if not compatible or not str(machine["hacked_by"]).is_empty():
			events.append({"type": "invalid_action", "id": hero_id, "requested": action, "reason": "incompatible_machine"})
			return {"actual": "WAIT", "push": null}

		hero["battery"] = int(hero["battery"]) - 1
		hero["hacking_machine"] = machine_id
		machine["hacked_by"] = hero_id

		# HACK annule un déplacement auto qui n'avait pas encore été exécuté.
		if str(pending_at_start.get(machine_id, "")) == "auto":
			pending_at_start.erase(machine_id)
			machine["pending_move"] = false
			machine["pending_source"] = ""

		state.heroes[hero_id] = hero
		state.machines[machine_id] = machine
		events.append({"type": "hack", "id": hero_id, "machine": machine_id})
		return {"actual": "HACK", "push": null}

	if action.begins_with("HACK_"):
		if hacking_machine.is_empty() or not state.machines.has(hacking_machine) or int(hero["battery"]) <= 0:
			return {"actual": "WAIT", "push": null}

		var machine: Dictionary = state.machines[hacking_machine]
		match action:
			"HACK_MOVE":
				if bool(machine["pending_move"]) or not _machine_forward_is_commandable(hacking_machine):
					return {"actual": "WAIT", "push": null}
				hero["battery"] = int(hero["battery"]) - 1
				machine["pending_move"] = true
				machine["pending_source"] = "hack"
				state.heroes[hero_id] = hero
				state.machines[hacking_machine] = machine
				events.append({"type": "machine_move_queued", "id": hacking_machine, "source": "hack"})
				return {"actual": action, "push": null}

			"HACK_CW":
				hero["battery"] = int(hero["battery"]) - 1
				machine["orientation"] = ActionRules.rotate_cw(str(machine["orientation"]))
				state.heroes[hero_id] = hero
				state.machines[hacking_machine] = machine
				events.append({"type": "rotate", "id": hacking_machine, "orientation": machine["orientation"]})
				return {"actual": action, "push": null}

			"HACK_CCW":
				hero["battery"] = int(hero["battery"]) - 1
				machine["orientation"] = ActionRules.rotate_ccw(str(machine["orientation"]))
				state.heroes[hero_id] = hero
				state.machines[hacking_machine] = machine
				events.append({"type": "rotate", "id": hacking_machine, "orientation": machine["orientation"]})
				return {"actual": action, "push": null}

			"HACK_FILL":
				if str(machine["kind"]) != "X":
					return {"actual": "WAIT", "push": null}
				var front: Vector2i = Vector2i(machine["pos"]) + ActionRules.orientation_to_vector(str(machine["orientation"]))
				if not state.in_bounds(front) or state.terrain_at(front) != "o":
					return {"actual": "WAIT", "push": null}
				hero["battery"] = int(hero["battery"]) - 1
				state.set_terrain(front, ".")
				state.heroes[hero_id] = hero
				events.append({"type": "fill", "id": hacking_machine, "pos": front})
				return {"actual": action, "push": null}

			"HACK_CUT":
				if str(machine["kind"]) != "G" or state.terrain_at(Vector2i(machine["pos"])) != "t":
					return {"actual": "WAIT", "push": null}
				hero["battery"] = int(hero["battery"]) - 1
				state.set_terrain(Vector2i(machine["pos"]), ".")
				state.heroes[hero_id] = hero
				events.append({"type": "cut", "id": hacking_machine, "pos": machine["pos"]})
				return {"actual": action, "push": null}

	if action == "WAIT":
		return {"actual": "WAIT", "push": null}

	return {"actual": "WAIT", "push": null}

func _unhack(hero_id: String, machine_id: String, reason: String, events: Array) -> void:
	if not state.heroes.has(hero_id) or not state.machines.has(machine_id):
		return
	var hero: Dictionary = state.heroes[hero_id]
	var machine: Dictionary = state.machines[machine_id]
	hero["hacking_machine"] = ""
	machine["hacked_by"] = ""
	machine["unhack_cooldown"] = 1
	state.heroes[hero_id] = hero
	state.machines[machine_id] = machine
	events.append({"type": "unhack", "id": hero_id, "machine": machine_id, "reason": reason})

func _hero_transition(hero_id: String, origin: Vector2i, action: String) -> Dictionary:
	var dir: Vector2i = ActionRules.DIRS[action]
	var next: Vector2i = origin + dir
	if not state.in_bounds(next):
		return {"ok": false, "reason": "out_of_bounds"}

	var terrain_symbol: String = state.terrain_at(next)

	if hero_id == "F":
		if terrain_symbol == "#" or terrain_symbol == "t":
			return {"ok": false, "reason": "blocked"}
		if terrain_symbol == "o":
			var landing: Vector2i = next + dir
			if not state.in_bounds(landing):
				return {"ok": false, "reason": "hop_out_of_bounds"}
			var landing_terrain: String = state.terrain_at(landing)
			if landing_terrain in ["#", "t", "o"]:
				return {"ok": false, "reason": "hop_blocked"}
			if not _hero_elevation_transition_allowed(origin, landing):
				return {"ok": false, "reason": "elevation"}
			return {"ok": true, "to": landing, "cost": 10, "style": "hop"}
		if not _hero_elevation_transition_allowed(origin, next):
			return {"ok": false, "reason": "elevation"}
		return {"ok": true, "to": next, "cost": _hero_move_stamina_cost(origin, next), "style": "move"}

	# Imahaki
	if terrain_symbol == "#" or terrain_symbol == "o":
		return {"ok": false, "reason": "blocked"}
	if terrain_symbol == "t":
		var landing_m: Vector2i = next + dir
		if not state.in_bounds(landing_m):
			return {"ok": false, "reason": "climb_out_of_bounds"}
		var landing_terrain_m: String = state.terrain_at(landing_m)
		if landing_terrain_m in ["#", "o", "t"]:
			return {"ok": false, "reason": "climb_blocked"}
		if not _hero_elevation_transition_allowed(origin, landing_m):
			return {"ok": false, "reason": "elevation"}
		return {"ok": true, "to": landing_m, "cost": 10, "style": "climb"}
	if not _hero_elevation_transition_allowed(origin, next):
		return {"ok": false, "reason": "elevation"}
	return {"ok": true, "to": next, "cost": _hero_move_stamina_cost(origin, next), "style": "move"}

func _hero_elevation_transition_allowed(origin: Vector2i, destination: Vector2i) -> bool:
	var from_level: int = state.elevation_at(origin)
	var to_level: int = state.elevation_at(destination)
	# Old maps without elevation remain a flat Z0 board.
	if from_level <= 0 and to_level <= 0:
		return true
	var delta: int = to_level - from_level
	# Addendum: climb max +2; descent max -4.
	return delta < 3 and delta > -5

func _hero_move_stamina_cost(origin: Vector2i, destination: Vector2i) -> int:
	var from_level: int = state.elevation_at(origin)
	var to_level: int = state.elevation_at(destination)
	if from_level <= 0 and to_level <= 0:
		return 1
	if to_level > from_level:
		return 3
	if to_level < from_level:
		return 0
	return 1

func _process_hacked_grappler_waits(actual: Dictionary, pending_at_start: Dictionary, events: Array) -> void:
	for hero_id in ["F", "M"]:
		if str(actual[hero_id]) != "WAIT":
			continue
		var hero: Dictionary = state.heroes[hero_id]
		var machine_id: String = str(hero["hacking_machine"])
		if machine_id.is_empty() or pending_at_start.has(machine_id) or not state.machines.has(machine_id):
			continue
		var machine: Dictionary = state.machines[machine_id]
		if str(machine["kind"]) == "G" and state.terrain_at(Vector2i(machine["pos"])) == "t":
			state.set_terrain(Vector2i(machine["pos"]), ".")
			events.append({"type": "cut", "id": machine_id, "pos": machine["pos"], "automatic": true})

func _build_machine_move_intents(pending_at_start: Dictionary) -> Dictionary:
	var intents: Dictionary = {}
	for machine_id_value in pending_at_start.keys():
		var machine_id: String = str(machine_id_value)
		if not state.machines.has(machine_id):
			continue

		var machine: Dictionary = state.machines[machine_id]
		machine["pending_move"] = false
		machine["pending_source"] = ""
		state.machines[machine_id] = machine

		var dir: Vector2i = ActionRules.orientation_to_vector(str(machine["orientation"]))
		var target: Vector2i = Vector2i(machine["pos"]) + dir
		intents[machine_id] = {
			"id": machine_id,
			"from": Vector2i(machine["pos"]),
			"to": target,
			"dir": dir,
			"source": str(pending_at_start[machine_id]),
			"chest_id": state.chest_at(target),
		}
	return intents

# -----------------------------------------------------------------------------
# Résolution simultanée machine + coffre
# -----------------------------------------------------------------------------

func _plan_simultaneous_machines_and_chests(machine_intents: Dictionary, hero_push_intents: Array) -> Dictionary:
	var machine_valid: Dictionary = _compute_machine_topology_valid(machine_intents, {})
	var push_plan: Dictionary = _empty_push_plan()

	# Validité monotone : une machine déclarée bloquée pendant cette résolution
	# ne redevient pas valide dans le même tick. Cela évite les oscillations.
	var max_iterations: int = maxi(2, machine_intents.size() + 2)
	for _iteration in range(max_iterations):
		var all_push_intents: Array = hero_push_intents.duplicate(true)
		for machine_id_value in machine_intents.keys():
			var machine_id: String = str(machine_id_value)
			if not bool(machine_valid.get(machine_id, false)):
				continue
			var intent: Dictionary = machine_intents[machine_id]
			var chest_id: String = str(intent["chest_id"])
			if not chest_id.is_empty():
				all_push_intents.append({
					"actor_key": "machine:%s" % machine_id,
					"actor_type": "machine",
					"actor_id": machine_id,
					"chest_id": chest_id,
					"dir": Vector2i(intent["dir"]),
				})

		push_plan = _plan_chest_pushes(all_push_intents)
		var reserved: Dictionary = push_plan.get("reserved_destinations", {})
		var new_topology: Dictionary = _compute_machine_topology_valid(machine_intents, reserved)
		var actor_success: Dictionary = push_plan.get("actor_success", {})
		var changed: bool = false

		for machine_id_value in machine_intents.keys():
			var machine_id: String = str(machine_id_value)
			var keep_valid: bool = bool(machine_valid.get(machine_id, false)) and bool(new_topology.get(machine_id, false))
			var intent: Dictionary = machine_intents[machine_id]
			var chest_id: String = str(intent["chest_id"])
			if keep_valid and not chest_id.is_empty():
				keep_valid = bool(actor_success.get("machine:%s" % machine_id, false))
			if keep_valid != bool(machine_valid.get(machine_id, false)):
				changed = true
			machine_valid[machine_id] = keep_valid

		if not changed:
			break

	# Recalcul final avec uniquement les machines réellement valides.
	var final_push_intents: Array = hero_push_intents.duplicate(true)
	for machine_id_value in machine_intents.keys():
		var machine_id: String = str(machine_id_value)
		if not bool(machine_valid.get(machine_id, false)):
			continue
		var intent: Dictionary = machine_intents[machine_id]
		var chest_id: String = str(intent["chest_id"])
		if not chest_id.is_empty():
			final_push_intents.append({
				"actor_key": "machine:%s" % machine_id,
				"actor_type": "machine",
				"actor_id": machine_id,
				"chest_id": chest_id,
				"dir": Vector2i(intent["dir"]),
			})

	push_plan = _plan_chest_pushes(final_push_intents)
	var final_actor_success: Dictionary = push_plan.get("actor_success", {})
	for machine_id_value in machine_intents.keys():
		var machine_id: String = str(machine_id_value)
		if not bool(machine_valid.get(machine_id, false)):
			continue
		var intent: Dictionary = machine_intents[machine_id]
		if not str(intent["chest_id"]).is_empty():
			machine_valid[machine_id] = bool(final_actor_success.get("machine:%s" % machine_id, false))

	return {
		"machine_valid": machine_valid,
		"push_plan": push_plan,
	}

func _empty_push_plan() -> Dictionary:
	return {
		"actor_success": {},
		"groups": {},
		"reserved_destinations": {},
	}

func _plan_chest_pushes(intents: Array) -> Dictionary:
	var plan: Dictionary = _empty_push_plan()
	var actor_success: Dictionary = plan["actor_success"]
	var groups: Dictionary = plan["groups"]
	var reserved: Dictionary = plan["reserved_destinations"]

	if intents.is_empty():
		return plan

	var by_chest: Dictionary = {}
	for intent_value in intents:
		var intent: Dictionary = intent_value
		var chest_id: String = str(intent["chest_id"])
		var actor_key: String = str(intent["actor_key"])
		if chest_id.is_empty() or not state.chests.has(chest_id):
			actor_success[actor_key] = false
			continue
		if not by_chest.has(chest_id):
			by_chest[chest_id] = []
		var group: Array = by_chest[chest_id]
		group.append(intent)
		by_chest[chest_id] = group

	# Construire d'abord chaque groupe.
	for chest_id_value in by_chest.keys():
		var chest_id: String = str(chest_id_value)
		var group: Array = by_chest[chest_id]
		var unique_dirs: Dictionary = {}
		for intent_value in group:
			var intent: Dictionary = intent_value
			var dir: Vector2i = Vector2i(intent["dir"])
			unique_dirs[_pos_key(dir)] = dir

		var success: bool = unique_dirs.size() == 1
		var from: Vector2i = Vector2i(state.chests[chest_id]["pos"])
		var to: Vector2i = from
		if success:
			var direction_values: Array = unique_dirs.values()
			var dir: Vector2i = Vector2i(direction_values[0])
			to = from + dir
			success = _chest_destination_is_valid(chest_id, to)
			if success:
				success = _chest_push_elevation_allowed(group, from, to)

		groups[chest_id] = {
			"success": success,
			"from": from,
			"to": to,
			"intents": group,
		}

	# Deux coffres différents ne peuvent pas finir sur la même cellule.
	var destination_counts: Dictionary = {}
	for chest_id_value in groups.keys():
		var chest_id: String = str(chest_id_value)
		var group_data: Dictionary = groups[chest_id]
		if not bool(group_data["success"]):
			continue
		var to: Vector2i = Vector2i(group_data["to"])
		var key: String = _pos_key(to)
		destination_counts[key] = int(destination_counts.get(key, 0)) + 1

	for chest_id_value in groups.keys():
		var chest_id: String = str(chest_id_value)
		var group_data: Dictionary = groups[chest_id]
		if bool(group_data["success"]):
			var to: Vector2i = Vector2i(group_data["to"])
			if int(destination_counts.get(_pos_key(to), 0)) > 1:
				group_data["success"] = false
				groups[chest_id] = group_data

	# Propager le résultat vers chaque acteur et réserver les destinations.
	for chest_id_value in groups.keys():
		var chest_id: String = str(chest_id_value)
		var group_data: Dictionary = groups[chest_id]
		var success: bool = bool(group_data["success"])
		for intent_value in group_data["intents"]:
			var intent: Dictionary = intent_value
			actor_success[str(intent["actor_key"])] = success
		if success:
			reserved[_pos_key(Vector2i(group_data["to"]))] = chest_id

	return plan

func _apply_chest_plan(plan: Dictionary, events: Array) -> void:
	var groups: Dictionary = plan.get("groups", {})
	for chest_id_value in groups.keys():
		var chest_id: String = str(chest_id_value)
		var group_data: Dictionary = groups[chest_id]
		if not bool(group_data["success"]) or not state.chests.has(chest_id):
			continue

		var chest: Dictionary = state.chests[chest_id]
		var from: Vector2i = Vector2i(group_data["from"])
		var to: Vector2i = Vector2i(group_data["to"])
		var terrain_symbol: String = state.terrain_at(to)
		var elevation_drop: int = state.elevation_at(from) - state.elevation_at(to)

		# Addendum: a chest falling by 5+ levels is destroyed, even into a bush.
		if elevation_drop >= 5:
			state.chests.erase(chest_id)
			state.lost_chests += 1
			events.append({"type": "chest_lost", "id": chest_id, "from": from, "to": to, "reason": "cliff"})
		elif terrain_symbol == "@":
			state.chests.erase(chest_id)
			state.hidden_chests += 1
			state.bush_chests[to] = int(state.bush_chests.get(to, 0)) + 1
			events.append({"type": "chest_hidden", "id": chest_id, "from": from, "to": to})
		elif terrain_symbol == "o":
			state.chests.erase(chest_id)
			state.lost_chests += 1
			events.append({"type": "chest_lost", "id": chest_id, "from": from, "to": to})
		else:
			chest["pos"] = to
			state.chests[chest_id] = chest
			events.append({"type": "chest_move", "id": chest_id, "from": from, "to": to, "style": "push"})

func _chest_destination_is_valid(chest_id: String, dest: Vector2i) -> bool:
	if not state.in_bounds(dest):
		return false
	var terrain_symbol: String = state.terrain_at(dest)
	if terrain_symbol == "#" or terrain_symbol == "t":
		return false
	var other_chest: String = state.chest_at(dest)
	if not other_chest.is_empty() and other_chest != chest_id:
		return false
	# Les machines bloquent les coffres. Les héros, eux, peuvent partager une case.
	if not state.machine_at(dest).is_empty():
		return false
	return true

func _compute_machine_topology_valid(intents: Dictionary, reserved_chest_destinations: Dictionary) -> Dictionary:
	var valid: Dictionary = {}
	var target_counts: Dictionary = {}

	for machine_id_value in intents.keys():
		var machine_id: String = str(machine_id_value)
		var intent: Dictionary = intents[machine_id]
		var target: Vector2i = Vector2i(intent["to"])
		var okay: bool = _machine_target_static_valid(machine_id, target, reserved_chest_destinations)
		valid[machine_id] = okay
		var key: String = _pos_key(target)
		target_counts[key] = int(target_counts.get(key, 0)) + 1

	for machine_id_value in intents.keys():
		var machine_id: String = str(machine_id_value)
		var target: Vector2i = Vector2i(intents[machine_id]["to"])
		if int(target_counts.get(_pos_key(target), 0)) > 1:
			valid[machine_id] = false

	var memo: Dictionary = {}
	for machine_id_value in intents.keys():
		var machine_id: String = str(machine_id_value)
		if bool(valid.get(machine_id, false)):
			valid[machine_id] = _machine_chain_can_move(machine_id, intents, valid, memo, {})

	return valid

func _machine_target_static_valid(machine_id: String, target: Vector2i, reserved_chest_destinations: Dictionary) -> bool:
	if not state.in_bounds(target):
		return false
	if reserved_chest_destinations.has(_pos_key(target)):
		return false

	var machine: Dictionary = state.machines[machine_id]
	var terrain_symbol: String = state.terrain_at(target)
	if str(machine["kind"]) == "X" and terrain_symbol in ["#", "t"]:
		return false
	if str(machine["kind"]) == "G" and terrain_symbol in ["#", "o"]:
		return false
	var dir: Vector2i = target - Vector2i(machine["pos"])
	if not _machine_look_ahead_clear(machine_id, target, dir):
		return false
	if not _machine_elevation_transition_allowed(Vector2i(machine["pos"]), target):
		return false
	return true

func _machine_chain_can_move(machine_id: String, intents: Dictionary, valid: Dictionary, memo: Dictionary, visiting: Dictionary) -> bool:
	if memo.has(machine_id):
		return bool(memo[machine_id])
	if visiting.has(machine_id):
		memo[machine_id] = false
		return false
	if not bool(valid.get(machine_id, false)):
		memo[machine_id] = false
		return false

	visiting[machine_id] = true
	var target: Vector2i = Vector2i(intents[machine_id]["to"])
	var occupant: String = state.machine_at(target)
	if occupant.is_empty():
		visiting.erase(machine_id)
		memo[machine_id] = true
		return true
	if not intents.has(occupant):
		visiting.erase(machine_id)
		memo[machine_id] = false
		return false

	var can_move: bool = _machine_chain_can_move(occupant, intents, valid, memo, visiting)
	visiting.erase(machine_id)
	memo[machine_id] = can_move
	return can_move

func _execute_machine_moves(intents: Dictionary, valid: Dictionary, events: Array) -> Dictionary:
	var moved: Dictionary = {}
	for machine_id_value in intents.keys():
		var machine_id: String = str(machine_id_value)
		var intent: Dictionary = intents[machine_id]
		var machine: Dictionary = state.machines[machine_id]

		if not bool(valid.get(machine_id, false)):
			moved[machine_id] = false
			if str(intent["source"]) == "auto" and str(machine["hacked_by"]).is_empty():
				_rotate_blocked_machine(machine_id, events)
			else:
				events.append({"type": "machine_blocked", "id": machine_id, "pos": machine["pos"]})
			continue

		var from: Vector2i = Vector2i(machine["pos"])
		var to: Vector2i = Vector2i(intent["to"])
		machine["pos"] = to

		# Le DIG tous les 5 pas appartient à la routine automatique de X.
		if str(machine["kind"]) == "X" and str(intent["source"]) == "auto":
			machine["steps_since_dig"] = int(machine["steps_since_dig"]) + 1

		state.machines[machine_id] = machine
		moved[machine_id] = true
		events.append({"type": "move", "id": machine_id, "from": from, "to": to, "style": "machine"})

		var picked: int = state.pickup_stones_by_machine(machine_id)
		if picked > 0:
			events.append({"type": "stone_pickup_machine", "id": machine_id, "count": picked})

		machine = state.machines[machine_id]
		var rider: String = str(machine["hacked_by"])
		if not rider.is_empty() and state.heroes.has(rider):
			var hero: Dictionary = state.heroes[rider]
			var hero_from: Vector2i = Vector2i(hero["pos"])
			hero["pos"] = to
			hero["visual_facing"] = str(machine["orientation"])
			state.heroes[rider] = hero
			events.append({"type": "move", "id": rider, "from": hero_from, "to": to, "style": "ride"})
	return moved

# -----------------------------------------------------------------------------
# Routines automatiques machines
# -----------------------------------------------------------------------------

func _process_automatic_machines(pending_at_start: Dictionary, _moved_machines: Dictionary, machine_positions_at_start: Dictionary, events: Array) -> void:
	var eligible: Dictionary = {}

	for machine_id_value in state.machines.keys():
		var machine_id: String = str(machine_id_value)
		if pending_at_start.has(machine_id):
			continue

		var machine: Dictionary = state.machines[machine_id]
		if not str(machine["hacked_by"]).is_empty() or bool(machine["pending_move"]):
			continue

		if int(machine["unhack_cooldown"]) > 0:
			machine["unhack_cooldown"] = int(machine["unhack_cooldown"]) - 1
			state.machines[machine_id] = machine
			events.append({"type": "unhack_wait", "id": machine_id})
			continue

		# Grappler : lorsqu'il est sur un arbre, son action de ce tick est CUT.
		if str(machine["kind"]) == "G" and state.terrain_at(Vector2i(machine["pos"])) == "t":
			state.set_terrain(Vector2i(machine["pos"]), ".")
			events.append({"type": "cut", "id": machine_id, "pos": machine["pos"], "automatic": true})
			continue

		# Excavator : après 5 pas AUTO, son action suivante est DIG.
		if str(machine["kind"]) == "X" and int(machine["steps_since_dig"]) >= 5:
			if state.terrain_at(Vector2i(machine["pos"])) == ".":
				state.set_terrain(Vector2i(machine["pos"]), "o")
			machine["steps_since_dig"] = 0
			state.machines[machine_id] = machine
			events.append({"type": "dig", "id": machine_id, "pos": machine["pos"]})
			continue

		var dir: Vector2i = ActionRules.orientation_to_vector(str(machine["orientation"]))
		eligible[machine_id] = {
			"to": Vector2i(machine["pos"]) + dir,
			"dir": dir,
		}

	var candidate_valid: Dictionary = {}
	var target_counts: Dictionary = {}

	for machine_id_value in eligible.keys():
		var machine_id: String = str(machine_id_value)
		var auto_target: Vector2i = Vector2i(eligible[machine_id]["to"])
		var auto_target_key: String = _pos_key(auto_target)
		var start_occupant: String = str(machine_positions_at_start.get(auto_target_key, ""))

		# Clarification synchronisation : si la machine devant était déjà dans sa
		# phase d'attente MOVE au début du tick, celle derrière est désynchronisée
		# et traite la case comme bloquée.
		var phase_blocked: bool = not start_occupant.is_empty() and pending_at_start.has(start_occupant)
		candidate_valid[machine_id] = (not phase_blocked) and _auto_queue_static_valid(machine_id, eligible[machine_id])
		target_counts[auto_target_key] = int(target_counts.get(auto_target_key, 0)) + 1

	for machine_id_value in eligible.keys():
		var machine_id: String = str(machine_id_value)
		var target: Vector2i = Vector2i(eligible[machine_id]["to"])
		if int(target_counts.get(_pos_key(target), 0)) > 1:
			candidate_valid[machine_id] = false

	var memo: Dictionary = {}
	for machine_id_value in eligible.keys():
		var machine_id: String = str(machine_id_value)
		if bool(candidate_valid.get(machine_id, false)):
			candidate_valid[machine_id] = _auto_chain_can_queue(machine_id, eligible, candidate_valid, memo, {})

	for machine_id_value in eligible.keys():
		var machine_id: String = str(machine_id_value)
		if bool(candidate_valid.get(machine_id, false)):
			var machine: Dictionary = state.machines[machine_id]
			machine["pending_move"] = true
			machine["pending_source"] = "auto"
			state.machines[machine_id] = machine
			events.append({"type": "machine_move_queued", "id": machine_id, "source": "auto"})
		else:
			_rotate_blocked_machine(machine_id, events)

func _auto_queue_static_valid(machine_id: String, candidate: Dictionary) -> bool:
	var target: Vector2i = Vector2i(candidate["to"])
	if not state.in_bounds(target):
		return false

	var machine: Dictionary = state.machines[machine_id]
	var terrain_symbol: String = state.terrain_at(target)
	if str(machine["kind"]) == "X" and terrain_symbol in ["#", "t"]:
		return false
	if str(machine["kind"]) == "G" and terrain_symbol in ["#", "o"]:
		return false
	var origin: Vector2i = Vector2i(machine["pos"])
	var dir: Vector2i = Vector2i(candidate["dir"])
	# Look-ahead is deliberately checked before elevation (addendum priority).
	if not _machine_look_ahead_clear(machine_id, target, dir):
		return false
	if not _machine_elevation_transition_allowed(origin, target):
		return false

	var chest_id: String = state.chest_at(target)
	if not chest_id.is_empty():
		var dest: Vector2i = target + Vector2i(candidate["dir"])
		if not _chest_destination_is_valid(chest_id, dest):
			return false
		var push_intents: Array = [{"actor_type": "machine"}]
		if not _chest_push_elevation_allowed(push_intents, target, dest):
			return false
	return true

func _auto_chain_can_queue(machine_id: String, eligible: Dictionary, valid: Dictionary, memo: Dictionary, visiting: Dictionary) -> bool:
	if memo.has(machine_id):
		return bool(memo[machine_id])
	if visiting.has(machine_id):
		memo[machine_id] = false
		return false
	if not bool(valid.get(machine_id, false)):
		memo[machine_id] = false
		return false

	visiting[machine_id] = true
	var target: Vector2i = Vector2i(eligible[machine_id]["to"])
	var occupant: String = state.machine_at(target)
	if occupant.is_empty():
		visiting.erase(machine_id)
		memo[machine_id] = true
		return true
	if not eligible.has(occupant):
		visiting.erase(machine_id)
		memo[machine_id] = false
		return false

	var a: Dictionary = state.machines[machine_id]
	var b: Dictionary = state.machines[occupant]
	if str(a["orientation"]) != str(b["orientation"]):
		visiting.erase(machine_id)
		memo[machine_id] = false
		return false

	var can_queue: bool = _auto_chain_can_queue(occupant, eligible, valid, memo, visiting)
	visiting.erase(machine_id)
	memo[machine_id] = can_queue
	return can_queue

func _rotate_blocked_machine(machine_id: String, events: Array) -> void:
	var machine: Dictionary = state.machines[machine_id]
	if str(machine["kind"]) == "X":
		machine["orientation"] = ActionRules.rotate_ccw(str(machine["orientation"]))
	else:
		machine["orientation"] = ActionRules.rotate_cw(str(machine["orientation"]))
	state.machines[machine_id] = machine
	events.append({"type": "rotate", "id": machine_id, "orientation": machine["orientation"], "automatic": true})

func _machine_forward_is_commandable(machine_id: String) -> bool:
	var machine: Dictionary = state.machines[machine_id]
	var dir: Vector2i = ActionRules.orientation_to_vector(str(machine["orientation"]))
	var target: Vector2i = Vector2i(machine["pos"]) + dir
	if not state.in_bounds(target):
		return false

	var terrain_symbol: String = state.terrain_at(target)
	if str(machine["kind"]) == "X" and terrain_symbol in ["#", "t"]:
		return false
	if str(machine["kind"]) == "G" and terrain_symbol in ["#", "o"]:
		return false
	if not _machine_look_ahead_clear(machine_id, target, dir):
		return false
	if not _machine_elevation_transition_allowed(Vector2i(machine["pos"]), target):
		return false

	# Une autre machine peut être devant ; la résolution simultanée du tick
	# d'exécution décidera si la chaîne entière peut avancer.
	var chest_id: String = state.chest_at(target)
	if not chest_id.is_empty():
		var chest_dest: Vector2i = target + dir
		if not _chest_destination_is_valid(chest_id, chest_dest):
			return false
		var push_intents: Array = [{"actor_type": "machine"}]
		if not _chest_push_elevation_allowed(push_intents, target, chest_dest):
			return false
	return true

func _machine_elevation_transition_allowed(origin: Vector2i, destination: Vector2i) -> bool:
	var from_level: int = state.elevation_at(origin)
	var to_level: int = state.elevation_at(destination)
	if from_level <= 0 and to_level <= 0:
		return true
	return absi(to_level - from_level) <= 4

func _chest_push_elevation_allowed(intents: Array, from: Vector2i, to: Vector2i) -> bool:
	var from_level: int = state.elevation_at(from)
	var to_level: int = state.elevation_at(to)
	if from_level <= 0 and to_level <= 0:
		return true
	var delta: int = to_level - from_level
	for intent_value in intents:
		var intent: Dictionary = intent_value
		var actor_type: String = str(intent.get("actor_type", ""))
		if actor_type == "hero" and delta > 0:
			return false
		if actor_type == "machine" and delta > 2:
			return false
	return true

func _machine_look_ahead_clear(machine_id: String, target: Vector2i, dir: Vector2i) -> bool:
	if dir == Vector2i.ZERO:
		return false
	var perpendicular := Vector2i(-dir.y, dir.x)
	var chest_id: String = state.chest_at(target)
	var machine_positions: Array = []
	var hero_sensitive: Array = []
	if chest_id.is_empty():
		machine_positions = [target + perpendicular, target + dir, target - perpendicular]
	else:
		var chest_dest: Vector2i = target + dir
		hero_sensitive = [target + perpendicular, chest_dest, target - perpendicular]
		machine_positions = hero_sensitive.duplicate()
		machine_positions.append(chest_dest + perpendicular)
		machine_positions.append(chest_dest + dir)
		machine_positions.append(chest_dest - perpendicular)

	for pos_value in machine_positions:
		var pos: Vector2i = Vector2i(pos_value)
		if not state.in_bounds(pos):
			continue
		var other: String = state.machine_at(pos)
		if not other.is_empty() and other != machine_id:
			return false

	if not chest_id.is_empty():
		for hero_id in ["F", "M"]:
			var hero_pos: Vector2i = Vector2i(state.heroes[hero_id]["pos"])
			if hero_sensitive.has(hero_pos):
				return false

	# Also protect the destination from a chest being pushed into it from a side.
	for side_dir in ActionRules.DIRS.values():
		var push_dir: Vector2i = Vector2i(side_dir)
		var adjacent_chest: Vector2i = target - push_dir
		var chest: String = state.chest_at(adjacent_chest)
		if chest.is_empty():
			continue
		var pusher_pos: Vector2i = adjacent_chest - push_dir
		for hero_id in ["F", "M"]:
			if Vector2i(state.heroes[hero_id]["pos"]) == pusher_pos:
				return false
	return true

func _pos_key(pos: Vector2i) -> String:
	return "%d,%d" % [pos.x, pos.y]

func _apply_rest_recovery(hero_id: String, actual_action: String, events: Array) -> void:
	var hero: Dictionary = state.heroes[hero_id]
	var is_resting: bool = actual_action == "WAIT" or actual_action == "HACK" or actual_action.begins_with("HACK_")
	if not is_resting:
		hero["rest_ticks"] = 0
		state.heroes[hero_id] = hero
		return

	if int(hero["stamina"]) >= 100:
		hero["rest_ticks"] = 0
		state.heroes[hero_id] = hero
		return

	hero["rest_ticks"] = int(hero["rest_ticks"]) + 1
	if int(hero["rest_ticks"]) >= 2:
		hero["stamina"] = mini(100, int(hero["stamina"]) + 1)
		hero["rest_ticks"] = int(hero["rest_ticks"]) - 2
		events.append({"type": "stamina_recover", "id": hero_id, "value": int(hero["stamina"])})
	state.heroes[hero_id] = hero
