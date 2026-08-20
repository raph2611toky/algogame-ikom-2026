extends Node

const DEMO_MAP := "res://data/maps/demo_simulation/map.txt"

func _ready() -> void:
	var parsed: Dictionary = MapLoader.load_from_file(DEMO_MAP)
	assert(bool(parsed.get("ok", false)), str(parsed.get("error", "map fictive invalide")))
	var data: Dictionary = parsed.get("data", {})
	assert(int(data.get("width", 0)) == 10, "Largeur fictive inattendue")
	assert(int(data.get("height", 0)) == 8, "Hauteur fictive inattendue")
	assert(bool(data.get("has_explicit_elevation", false)), "elevation.txt n'a pas été chargé")
	assert(int(data.get("max_elevation", 0)) >= 8, "Élévation max fictive invalide")

	var simulation: Dictionary = LocalSimulationRunner.run(data, "fictive_dynamic_demo")
	var ticks: Array = simulation.get("ticks", [])
	assert(not ticks.is_empty(), "La simulation fictive n'a produit aucun tick")
	assert(ticks.size() <= int(data.get("time_limit", 0)), "Trop de ticks générés")
	assert(str(simulation.get("actions_txt", "")).ends_with("END_GAME\n"), "actions.txt doit finir par END_GAME")
	assert(simulation.has("initial_state"), "Snapshot initial absent")
	assert(simulation.has("result"), "Résultat final absent")

	var movement_events: int = 0
	var terrain_events: int = 0
	for tick_value in ticks:
		var tick: Dictionary = tick_value
		for event_value in tick.get("events", []):
			var event: Dictionary = event_value
			var kind: String = str(event.get("type", ""))
			if kind in ["move", "chest_move"]:
				movement_events += 1
			if kind in ["dig", "fill", "cut"]:
				terrain_events += 1

	var result: Dictionary = simulation.get("result", {})
	print("FICTIVE SIMULATION V19 OK • ticks=", ticks.size(), " • mouvements=", movement_events, " • terrain=", terrain_events, " • score=", int(result.get("score", 0)))
