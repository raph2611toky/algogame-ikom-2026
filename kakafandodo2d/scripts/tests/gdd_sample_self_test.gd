extends Node

# Scène de diagnostic optionnelle : exécute les 20 actions de l'annexe du GDD.
# Elle n'est pas la scène principale du projet. Ouvrez
# res://scenes/tests/GDDSampleSelfTest.tscn et lancez F6 pour diagnostiquer.

func _ready() -> void:
	var result: Dictionary = MapLoader.load_from_file("res://data/maps/example_map.txt")
	assert(bool(result["ok"]), String(result["error"]))

	var pairs: Array = [
		{"F":"LEFT", "M":"LEFT"},
		{"F":"UP", "M":"LEFT"},
		{"F":"RIGHT", "M":"HACK"},
		{"F":"RIGHT", "M":"HACK_MOVE"},
		{"F":"RIGHT", "M":"WAIT"},
		{"F":"RIGHT", "M":"HACK_MOVE"},
		{"F":"RIGHT", "M":"WAIT"},
		{"F":"WAIT", "M":"HACK_MOVE"},
		{"F":"WAIT", "M":"WAIT"},
		{"F":"HACK", "M":"HACK_CW"},
		{"F":"HACK_CCW", "M":"HACK_MOVE"},
		{"F":"HACK_MOVE", "M":"WAIT"},
		{"F":"WAIT", "M":"WAIT"},
		{"F":"HACK_MOVE", "M":"HACK_CCW"},
		{"F":"WAIT", "M":"HACK_MOVE"},
		{"F":"HACK_CW", "M":"WAIT"},
		{"F":"HACK_MOVE", "M":"WAIT"},
		{"F":"WAIT", "M":"HACK_CCW"},
		{"F":"HACK_MOVE", "M":"HACK_MOVE"},
		{"F":"WAIT", "M":"WAIT"},
	]

	var replay_brain: ActionSequenceBrain = ActionSequenceBrain.new(pairs)
	var simulation: SimulationEngine = SimulationEngine.new()
	var state: GameState = simulation.initialize(result["data"], replay_brain)
	for _tick_index in range(20):
		simulation.step()

	print("--- GDD SAMPLE SELF TEST ---")
	print("F: ", state.heroes["F"])
	print("M: ", state.heroes["M"])
	print("X0: ", state.machines.get("X0", {}))
	print("G0: ", state.machines.get("G0", {}))
	print("score actuel: ", state.score())

	# Valeurs de référence de l'annexe du GDD, pages 13–16.
	assert(state.heroes["F"]["pos"] == Vector2i(4, 0), "Position finale F différente du GDD")
	assert(int(state.heroes["F"]["stamina"]) == 81, "Stamina finale F différente du GDD")
	assert(int(state.heroes["F"]["battery"]) == 93, "Batterie finale F différente du GDD")
	assert(state.heroes["M"]["pos"] == Vector2i(5, 0), "Position finale M différente du GDD")
	assert(int(state.heroes["M"]["stamina"]) == 100, "Stamina finale M différente du GDD")
	assert(int(state.heroes["M"]["battery"]) == 90, "Batterie finale M différente du GDD")
	assert(state.machines["X0"]["pos"] == Vector2i(4, 0), "Position finale X différente du GDD")
	assert(String(state.machines["X0"]["orientation"]) == "UP", "Orientation finale X différente du GDD")
	assert(state.machines["G0"]["pos"] == Vector2i(5, 0), "Position finale G différente du GDD")
	assert(String(state.machines["G0"]["orientation"]) == "UP", "Orientation finale G différente du GDD")
	print("SELF TEST OK")
