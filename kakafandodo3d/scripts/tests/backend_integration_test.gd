extends Node

# Ancien test d'intégration réseau converti en smoke-test local pour l'édition 3D hors-ligne.
func _ready() -> void:
	var parsed: Dictionary = MapLoader.load_from_file("res://data/maps/example_map.txt")
	assert(bool(parsed.get("ok", false)), str(parsed.get("error", "map invalide")))
	var data: Dictionary = parsed.get("data", {})
	assert(not data.is_empty(), "Données de carte absentes")
	var simulation: Dictionary = LocalSimulationRunner.run(data, "offline_smoke_test")
	assert(not simulation.is_empty(), "Simulation locale vide")
	assert(simulation.has("initial_state"), "Snapshot initial absent")
	assert(simulation.has("ticks"), "Ticks locaux absents")
	print("LOCAL 3D SMOKE TEST OK • ticks=", simulation.get("ticks", []).size())
