class_name ActionRules
extends RefCounted

const DIRS := {
	"UP": Vector2i(0, -1),
	"DOWN": Vector2i(0, 1),
	"LEFT": Vector2i(-1, 0),
	"RIGHT": Vector2i(1, 0),
}

const HERO_ACTIONS := [
	"UP", "DOWN", "LEFT", "RIGHT", "WAIT",
	"PUSH_UP", "PUSH_DOWN", "PUSH_LEFT", "PUSH_RIGHT",
	"HACK", "HACK_MOVE", "HACK_FILL", "HACK_CUT", "HACK_CW", "HACK_CCW"
]

static func rotate_cw(orientation: String) -> String:
	match orientation:
		"UP": return "RIGHT"
		"RIGHT": return "DOWN"
		"DOWN": return "LEFT"
		_: return "UP"

static func rotate_ccw(orientation: String) -> String:
	match orientation:
		"UP": return "LEFT"
		"LEFT": return "DOWN"
		"DOWN": return "RIGHT"
		_: return "UP"

static func dir_for_action(action: String) -> Vector2i:
	var key := action
	if key.begins_with("PUSH_"):
		key = key.trim_prefix("PUSH_")
	return DIRS.get(key, Vector2i.ZERO)

static func orientation_to_vector(orientation: String) -> Vector2i:
	return DIRS.get(orientation, Vector2i.ZERO)
