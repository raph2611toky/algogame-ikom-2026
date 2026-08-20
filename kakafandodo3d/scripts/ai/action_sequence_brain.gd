class_name ActionSequenceBrain
extends RefCounted

var action_pairs: Array = []
var cursor: int = 0

func _init(pairs: Array = []) -> void:
	action_pairs = pairs.duplicate(true)

func get_actions(_state: GameState) -> Dictionary:
	if cursor >= action_pairs.size():
		return {"F": "WAIT", "M": "WAIT"}
	var pair: Dictionary = action_pairs[cursor]
	cursor += 1
	return {
		"F": str(pair.get("F", "WAIT")),
		"M": str(pair.get("M", "WAIT")),
	}
