class_name ActionsWriter
extends RefCounted

static func write_default(state: GameState) -> String:
	return write_to_path(state, "user://actions.txt")

static func write_to_path(state: GameState, path: String) -> String:
	var validation: Dictionary = validate_history(state)
	if not bool(validation.get("ok", false)):
		push_error(String(validation.get("error", "Historique actions invalide.")))
		return ""
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	for line in state.action_history:
		file.store_line(line)
	file.store_line("END_GAME")
	file.close()
	return ProjectSettings.globalize_path(path) if path.begins_with("user://") or path.begins_with("res://") else path

static func export_existing(source_path: String, destination_path: String) -> bool:
	if source_path.is_empty() or destination_path.is_empty():
		return false
	var source: FileAccess = FileAccess.open(source_path, FileAccess.READ)
	if source == null:
		return false
	var content: String = source.get_as_text()
	source.close()
	var target: FileAccess = FileAccess.open(destination_path, FileAccess.WRITE)
	if target == null:
		return false
	target.store_string(content)
	target.close()
	return true

static func read_text(path: String) -> String:
	if path.is_empty():
		return ""
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var text: String = file.get_as_text()
	file.close()
	return text

static func validate_history(state: GameState) -> Dictionary:
	if state.action_history.size() > state.time_limit:
		return {"ok": false, "error": "actions.txt dépasserait la limite de %d ticks." % state.time_limit}
	for index in range(state.action_history.size()):
		var line: String = state.action_history[index]
		var parts: PackedStringArray = line.split("|", false)
		if parts.size() != 2:
			return {"ok": false, "error": "Action tick %d invalide : %s" % [index + 1, line]}
		var action_f: String = String(parts[0]).strip_edges()
		var action_m: String = String(parts[1]).strip_edges()
		if not _valid_action(action_f) or not _valid_action(action_m):
			return {"ok": false, "error": "Action inconnue au tick %d : %s" % [index + 1, line]}
	return {"ok": true, "error": ""}

static func _valid_action(action: String) -> bool:
	return action in [
		"UP", "DOWN", "LEFT", "RIGHT", "WAIT",
		"PUSH_UP", "PUSH_DOWN", "PUSH_LEFT", "PUSH_RIGHT",
		"HACK", "HACK_MOVE", "HACK_FILL", "HACK_CUT", "HACK_CW", "HACK_CCW"
	]
