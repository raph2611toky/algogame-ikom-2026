class_name GameBoard
extends Control

const FLOOR_TEXTURE: Texture2D = preload("res://assets/game/terrain/floor.svg")
const ROCK_TEXTURE: Texture2D = preload("res://assets/game/terrain/rock.svg")
const TREE_TEXTURE: Texture2D = preload("res://assets/game/terrain/tree.svg")
const HOLE_TEXTURE: Texture2D = preload("res://assets/game/terrain/hole.svg")
const BUSH_TEXTURE: Texture2D = preload("res://assets/game/terrain/bush.svg")
const GEM_BLUE: Texture2D = preload("res://assets/game/props/gem_blue.svg")
const GEM_RED: Texture2D = preload("res://assets/game/props/gem_red.svg")
const GEM_GREEN: Texture2D = preload("res://assets/game/props/gem_green.svg")
const GEM_GOLD: Texture2D = preload("res://assets/game/props/gem_gold.svg")
const PARTICLE_DOT: Texture2D = preload("res://assets/game/effects/particle_dot.svg")
const EFFECT_PULSE_SCRIPT = preload("res://scripts/game/effect_pulse.gd")

# Rendu 2D-extended : chaque niveau d elevation ajoute une "croûte" visible.
# La grille reste top-down et lisible, mais la surface de la cellule monte.
const ELEVATION_LAYER_RATIO := 0.085
const CRUST_TOP := Color("#765338")
const CRUST_BOTTOM := Color("#432d20")
const CRUST_LINE := Color("#2f2017")

var state_ref: GameState
var entity_nodes: Dictionary = {}
var _cell_size: float = 64.0
var _origin: Vector2 = Vector2.ZERO
var _layer_height: float = 0.0
var _elevation_headroom: float = 0.0
var visual_effects_strength: float = 1.0

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip_contents = true

func set_effects_percent(percent: int) -> void:
	visual_effects_strength = clampf(float(percent) / 100.0, 0.0, 1.0)

func set_state(new_state: GameState, events: Array = [], animation_duration: float = 0.12) -> void:
	state_ref = new_state
	_recompute_geometry()
	queue_redraw()
	_sync_entities(events, animation_duration)
	_play_entity_reactions(events)
	_emit_event_effects(events)

func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and state_ref != null:
		_recompute_geometry()
		queue_redraw()
		_sync_entities([], 0.0)

func _recompute_geometry() -> void:
	if state_ref == null or state_ref.width <= 0 or state_ref.height <= 0:
		return
	var available: Vector2 = size - Vector2(42.0, 42.0)
	var max_level := state_ref.max_elevation if state_ref.has_elevation else 0
	var effective_height_cells := float(state_ref.height) + float(max_level) * ELEVATION_LAYER_RATIO
	_cell_size = minf(
		available.x / float(state_ref.width),
		available.y / maxf(1.0, effective_height_cells)
	)
	_cell_size = clampf(_cell_size, 18.0, 112.0)
	_layer_height = minf(10.0, _cell_size * ELEVATION_LAYER_RATIO) if max_level > 0 else 0.0
	_elevation_headroom = float(max_level) * _layer_height
	var board_width := _cell_size * state_ref.width
	var visual_height := _cell_size * state_ref.height + _elevation_headroom
	# _origin représente le coin supérieur gauche de la grille au niveau 0.
	# On réserve au-dessus la place nécessaire aux cellules les plus hautes.
	_origin = Vector2(
		(size.x - board_width) * 0.5,
		(size.y - visual_height) * 0.5 + _elevation_headroom
	)

func _draw() -> void:
	if state_ref == null:
		return
	var board_width := _cell_size * state_ref.width
	var visual_height := _cell_size * state_ref.height + _elevation_headroom
	var frame_position := _origin - Vector2(0.0, _elevation_headroom) - Vector2(12.0, 12.0)
	var frame_rect := Rect2(frame_position, Vector2(board_width, visual_height) + Vector2(24.0, 24.0))
	draw_rect(frame_rect, Color("#38271b"), true)
	draw_rect(frame_rect, Color("#17100b"), false, 5.0)
	draw_rect(Rect2(frame_rect.position + Vector2(6.0, 6.0), frame_rect.size - Vector2(12.0, 12.0)), Color("#8b623b"), false, 2.0)

	# Dessin arrière -> avant. Une cellule de niveau N reçoit exactement N
	# bandes de croûte sous sa surface supérieure.
	for y in range(state_ref.height):
		for x in range(state_ref.width):
			var pos: Vector2i = Vector2i(x, y)
			var rect: Rect2 = _cell_rect(pos)
			_draw_elevation_stack(pos, rect)
			_draw_floor(rect, (x + y) % 2 == 0)
			_draw_terrain(pos, rect)
			_draw_elevation_badge(pos, rect)
			if int(state_ref.stones.get(pos, 0)) > 0:
				_draw_stone(pos, rect)
			if state_ref.terrain_at(pos) == "@" and int(state_ref.bush_chests.get(pos, 0)) > 0:
				_draw_bush_count(rect, int(state_ref.bush_chests[pos]))

func _draw_elevation_stack(pos: Vector2i, top_rect: Rect2) -> void:
	if not state_ref.has_elevation or _layer_height <= 0.0:
		return
	var level := state_ref.elevation_at(pos)
	if level <= 0:
		return
	for layer in range(level):
		var ratio := float(layer) / float(maxi(1, level - 1)) if level > 1 else 0.0
		var color := CRUST_TOP.lerp(CRUST_BOTTOM, ratio)
		var band := Rect2(
			Vector2(top_rect.position.x, top_rect.end.y + float(layer) * _layer_height),
			Vector2(top_rect.size.x, _layer_height + 0.8)
		)
		draw_rect(band, color, true)
		draw_line(band.position, Vector2(band.end.x, band.position.y), CRUST_LINE, maxf(0.8, _cell_size * 0.012))
		draw_line(Vector2(band.position.x, band.position.y), Vector2(band.position.x, band.end.y), CRUST_LINE, maxf(0.8, _cell_size * 0.010))
		draw_line(Vector2(band.end.x, band.position.y), band.end, CRUST_LINE, maxf(0.8, _cell_size * 0.010))

func _draw_elevation_badge(pos: Vector2i, rect: Rect2) -> void:
	if not state_ref.has_elevation or rect.size.x < 34.0:
		return
	var level := state_ref.elevation_at(pos)
	if level <= 0:
		return
	var font: Font = ThemeDB.fallback_font
	var font_size := maxi(8, int(rect.size.x * 0.13))
	var label_pos := rect.position + Vector2(rect.size.x * 0.06, rect.size.y * 0.18)
	draw_string(font, label_pos, str(level), HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size, Color(0.20, 0.14, 0.09, 0.72))

func _draw_floor(rect: Rect2, alternate: bool) -> void:
	var modulate_color: Color = Color(0.94, 0.91, 0.85, 1.0) if alternate else Color(0.87, 0.82, 0.74, 1.0)
	draw_texture_rect(FLOOR_TEXTURE, rect, false, modulate_color)
	draw_rect(rect, Color(0.20, 0.14, 0.09, 0.42), false, maxf(1.0, _cell_size * 0.018))

func _draw_terrain(pos: Vector2i, rect: Rect2) -> void:
	var symbol: String = state_ref.terrain_at(pos)
	var texture: Texture2D
	match symbol:
		"#": texture = ROCK_TEXTURE
		"t": texture = TREE_TEXTURE
		"o": texture = HOLE_TEXTURE
		"@": texture = BUSH_TEXTURE
		_: return

	var margin: float = _cell_size * 0.06
	var target_rect: Rect2 = Rect2(rect.position + Vector2(margin, margin), rect.size - Vector2(margin * 2.0, margin * 2.0))
	if symbol == "t":
		target_rect = Rect2(rect.position + Vector2(_cell_size * 0.02, -_cell_size * 0.10), rect.size + Vector2(-_cell_size * 0.04, _cell_size * 0.10))
	draw_texture_rect(texture, target_rect, false)

func _draw_stone(pos: Vector2i, rect: Rect2) -> void:
	var index: int = absi(pos.x * 13 + pos.y * 7) % 4
	var texture: Texture2D
	match index:
		0: texture = GEM_BLUE
		1: texture = GEM_RED
		2: texture = GEM_GREEN
		_: texture = GEM_GOLD
	var target_size: Vector2 = rect.size * 0.58
	var target_rect: Rect2 = Rect2(rect.get_center() - target_size * 0.5 + Vector2(0.0, rect.size.y * 0.04), target_size)
	draw_texture_rect(texture, target_rect, false)

func _draw_bush_count(rect: Rect2, count: int) -> void:
	if rect.size.x < 22.0:
		return
	var font: Font = ThemeDB.fallback_font
	var badge_center: Vector2 = rect.position + Vector2(rect.size.x * 0.78, rect.size.y * 0.23)
	var badge_radius: float = rect.size.x * 0.14
	draw_circle(badge_center, badge_radius, Color("#3a2415"))
	draw_circle(badge_center, badge_radius, Color("#d9a557"), false, maxf(1.0, rect.size.x * 0.025))
	var font_size: int = maxi(8, int(rect.size.x * 0.18))
	draw_string(font, badge_center + Vector2(-badge_radius, font_size * 0.35), str(count), HORIZONTAL_ALIGNMENT_CENTER, badge_radius * 2.0, font_size, Color("#f6dfb2"))

func _sync_entities(events: Array, duration: float) -> void:
	if state_ref == null:
		return

	var desired: Dictionary = {}
	for hero_id in ["F", "M"]:
		var hero_data: Dictionary = state_ref.heroes[hero_id]
		desired[hero_id] = {
			"kind": hero_id,
			"pos": Vector2i(hero_data["pos"]),
			"facing": str(hero_data.get("visual_facing", "DOWN")),
			"hacked": not str(hero_data.get("hacking_machine", "")).is_empty(),
			"pending": false,
			"action": str(hero_data.get("last_action", "WAIT")),
		}
	for machine_id_value in state_ref.machines.keys():
		var machine_id: String = str(machine_id_value)
		var machine_data: Dictionary = state_ref.machines[machine_id]
		desired[machine_id] = {
			"kind": str(machine_data["kind"]),
			"pos": Vector2i(machine_data["pos"]),
			"facing": str(machine_data["orientation"]),
			"hacked": not str(machine_data.get("hacked_by", "")).is_empty(),
			"pending": bool(machine_data.get("pending_move", false)),
			"action": "WAIT",
		}
	for chest_id_value in state_ref.chests.keys():
		var chest_id: String = str(chest_id_value)
		var chest_data: Dictionary = state_ref.chests[chest_id]
		desired[chest_id] = {
			"kind": "C",
			"pos": Vector2i(chest_data["pos"]),
			"facing": "",
			"hacked": false,
			"pending": false,
			"action": "WAIT",
		}

	var event_styles: Dictionary = {}
	var removal_events: Dictionary = {}
	for event_value in events:
		var event_data: Dictionary = event_value
		var event_id: String = str(event_data.get("id", ""))
		if event_id.is_empty():
			continue
		var event_type: String = str(event_data.get("type", ""))
		if event_type == "move" or event_type == "chest_move":
			event_styles[event_id] = str(event_data.get("style", "move"))
		elif event_type == "chest_hidden" or event_type == "chest_lost":
			removal_events[event_id] = event_data

	for entity_id_value in desired.keys():
		var entity_id: String = str(entity_id_value)
		var spec: Dictionary = desired[entity_id]
		var entity_view: EntityView
		var is_new: bool = not entity_nodes.has(entity_id)
		if is_new:
			entity_view = EntityView.new()
			entity_view.setup(str(spec["kind"]), entity_id)
			add_child(entity_view)
			entity_nodes[entity_id] = entity_view
		else:
			entity_view = entity_nodes[entity_id] as EntityView

		entity_view.size = Vector2(_cell_size * 0.88, _cell_size * 0.88)
		entity_view.pivot_offset = entity_view.size / 2.0
		entity_view.queue_redraw()
		var entity_pos := Vector2i(spec["pos"])
		var elevation_z := state_ref.elevation_at(entity_pos) if state_ref.has_elevation else 0
		entity_view.z_index = _z_for_kind(str(spec["kind"])) + entity_pos.y * 12 + elevation_z * 2
		entity_view.set_visual_state(
			str(spec.get("facing", "")),
			bool(spec.get("hacked", false)),
			bool(spec.get("pending", false)),
			str(spec.get("action", "WAIT"))
		)
		var target_position: Vector2 = _cell_center(Vector2i(spec["pos"])) - entity_view.size / 2.0

		if is_new:
			entity_view.position = target_position
			if duration > 0.0:
				entity_view.modulate.a = 0.0
				var appear_tween: Tween = create_tween()
				appear_tween.tween_property(entity_view, "modulate:a", 1.0, minf(duration, 0.12))
			else:
				entity_view.modulate.a = 1.0
		else:
			entity_view.animate_to(target_position, duration, str(event_styles.get(entity_id, "move")))

	var stale_ids: Array[String] = []
	for entity_id_value in entity_nodes.keys():
		var entity_id: String = str(entity_id_value)
		if desired.has(entity_id):
			continue
		var stale_view: EntityView = entity_nodes[entity_id] as EntityView
		if removal_events.has(entity_id):
			var removal_event: Dictionary = removal_events[entity_id]
			var removal_target: Vector2 = _cell_center(Vector2i(removal_event["to"])) - stale_view.size / 2.0
			stale_view.animate_to(removal_target, duration, "move")
			stale_view.fade_out_and_free(maxf(0.08, duration))
		else:
			stale_view.queue_free()
		stale_ids.append(entity_id)
	for stale_id in stale_ids:
		entity_nodes.erase(stale_id)

func cell_center_local(pos: Vector2i) -> Vector2:
	return _cell_center(pos)

func _play_entity_reactions(events: Array) -> void:
	for event_value in events:
		var event_data: Dictionary = event_value
		var event_type: String = str(event_data.get("type", ""))
		var event_id: String = str(event_data.get("id", ""))
		if event_type == "hack":
			var machine_id: String = str(event_data.get("machine", ""))
			if entity_nodes.has(machine_id):
				var machine_view: EntityView = entity_nodes[machine_id] as EntityView
				machine_view.play_reaction("hack")
			if entity_nodes.has(event_id):
				var hero_view: EntityView = entity_nodes[event_id] as EntityView
				hero_view.play_reaction("hack")
		elif event_type == "rotate" and entity_nodes.has(event_id):
			var rotate_view: EntityView = entity_nodes[event_id] as EntityView
			rotate_view.play_reaction("rotate")
		elif event_type == "machine_blocked" and entity_nodes.has(event_id):
			var blocked_view: EntityView = entity_nodes[event_id] as EntityView
			blocked_view.play_reaction("blocked")

func _emit_event_effects(events: Array) -> void:
	if state_ref == null or visual_effects_strength <= 0.02:
		return
	for event_value in events:
		var event_data: Dictionary = event_value
		var event_type: String = str(event_data.get("type", ""))
		var pos: Vector2i = _event_cell(event_data)
		if pos.x < 0 or pos.y < 0:
			continue
		match event_type:
			"hack":
				_spawn_particles(pos, Color("#59dcff"), 26, Vector2(0.0, -1.0), 115.0, 58.0, 130.0, 0.42)
				_spawn_pulse(pos, Color("#7ee8ff"), "HACK")
			"dig":
				_spawn_particles(pos, Color("#9f7249"), 24, Vector2(0.0, -1.0), 145.0, 44.0, 115.0, 0.40)
				_spawn_pulse(pos, Color("#d1a06a"), "DIG")
			"cut":
				_spawn_particles(pos, Color("#72b857"), 22, Vector2(0.0, -1.0), 150.0, 50.0, 120.0, 0.42)
				_spawn_pulse(pos, Color("#a4db78"), "CUT")
			"fill":
				_spawn_particles(pos, Color("#7cb5ce"), 20, Vector2(0.0, -1.0), 135.0, 42.0, 105.0, 0.40)
				_spawn_pulse(pos, Color("#a7d8e9"), "FILL")
			"stone_pickup", "stone_steal", "stone_pickup_machine":
				_spawn_particles(pos, Color("#ffe07a"), 18, Vector2(0.0, -1.0), 175.0, 55.0, 135.0, 0.34)
				_spawn_pulse(pos, Color("#fff0a6"), "+")
			"chest_hidden":
				_spawn_particles(pos, Color("#83cf66"), 28, Vector2(0.0, -1.0), 180.0, 58.0, 145.0, 0.48)
				_spawn_pulse(pos, Color("#b4ef91"), "CACHÉ")
			"chest_lost":
				_spawn_particles(pos, Color("#6c4431"), 26, Vector2(0.0, -1.0), 150.0, 45.0, 110.0, 0.48)
				_spawn_pulse(pos, Color("#d88465"), "PERDU")
			"move":
				var style: String = str(event_data.get("style", "move"))
				if style == "hop" or style == "climb":
					_spawn_particles(pos, Color(0.92, 0.86, 0.70, 1.0), 10, Vector2(0.0, -1.0), 125.0, 28.0, 72.0, 0.24)
			"invalid_action":
				_spawn_pulse(pos, Color("#ff765f"), "!")
			_:
				pass

func _event_cell(event_data: Dictionary) -> Vector2i:
	if event_data.has("pos"):
		return Vector2i(event_data["pos"])
	if event_data.has("to"):
		return Vector2i(event_data["to"])
	var id: String = str(event_data.get("id", ""))
	if state_ref.heroes.has(id):
		return Vector2i(state_ref.heroes[id]["pos"])
	if state_ref.machines.has(id):
		return Vector2i(state_ref.machines[id]["pos"])
	if state_ref.chests.has(id):
		return Vector2i(state_ref.chests[id]["pos"])
	var machine_id: String = str(event_data.get("machine", ""))
	if state_ref.machines.has(machine_id):
		return Vector2i(state_ref.machines[machine_id]["pos"])
	return Vector2i(-1, -1)

func _spawn_particles(pos: Vector2i, color: Color, amount: int, direction: Vector2, spread: float, velocity_min: float, velocity_max: float, lifetime: float) -> void:
	var particles := CPUParticles2D.new()
	particles.texture = PARTICLE_DOT
	particles.position = _cell_center(pos)
	particles.z_index = 140
	particles.amount = maxi(2, int(round(float(amount) * visual_effects_strength)))
	particles.lifetime = lifetime
	particles.one_shot = true
	particles.explosiveness = 0.92
	particles.direction = direction
	particles.spread = spread
	particles.gravity = Vector2(0.0, 150.0)
	particles.initial_velocity_min = velocity_min
	particles.initial_velocity_max = velocity_max
	particles.scale_amount_min = 0.18
	particles.scale_amount_max = 0.52
	particles.color = color
	particles.local_coords = true
	particles.emitting = false
	add_child(particles)
	particles.emitting = true
	particles.restart()
	var cleanup_timer := get_tree().create_timer(lifetime + 0.35)
	cleanup_timer.timeout.connect(particles.queue_free)

func _spawn_pulse(pos: Vector2i, color: Color, caption: String) -> void:
	var pulse: BoardEffectPulse = EFFECT_PULSE_SCRIPT.new() as BoardEffectPulse
	pulse.setup(color, caption, maxf(14.0, _cell_size * 0.28))
	pulse.position = _cell_center(pos) - pulse.size * 0.5
	pulse.z_index = 160
	add_child(pulse)
	pulse.play()

func _cell_rect(pos: Vector2i) -> Rect2:
	var elevation_offset := 0.0
	if state_ref != null and state_ref.has_elevation:
		elevation_offset = float(state_ref.elevation_at(pos)) * _layer_height
	var base_position := _origin + Vector2(pos.x, pos.y) * _cell_size
	return Rect2(base_position - Vector2(0.0, elevation_offset), Vector2(_cell_size, _cell_size))

func _cell_center(pos: Vector2i) -> Vector2:
	return _cell_rect(pos).get_center()

func _z_for_kind(kind: String) -> int:
	match kind:
		"C": return 30
		"X", "G": return 50
		"F", "M": return 70
		_: return 10
