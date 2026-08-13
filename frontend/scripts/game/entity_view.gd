class_name EntityView
extends Control

const IKOTOFOSA_TEXTURE: Texture2D = preload("res://assets/game/characters/ikotofosa_board.png")
const IMAHAKI_TEXTURE: Texture2D = preload("res://assets/game/characters/imahaki_board.png")
const EXCAVATOR_TEXTURE: Texture2D = preload("res://assets/game/machines/excavator.svg")
const GRAPPLER_TEXTURE: Texture2D = preload("res://assets/game/machines/grappler.svg")
const CHEST_TEXTURE: Texture2D = preload("res://assets/game/props/chest.svg")

var entity_kind: String = ""
var entity_id: String = ""
var facing: String = "RIGHT"
var hacked: bool = false
var pending_move: bool = false
var last_action: String = "WAIT"
var _phase: float = 0.0
var _flash: float = 0.0

func setup(kind: String, id: String) -> void:
	entity_kind = kind
	entity_id = id
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_phase = randf_range(0.0, TAU)
	set_process(entity_kind in ["F", "M", "X", "G"])
	queue_redraw()

func set_visual_state(new_facing: String, is_hacked: bool, is_pending: bool, action: String = "WAIT") -> void:
	if not new_facing.is_empty():
		facing = new_facing
	if is_hacked and not hacked:
		_flash = 1.0
	hacked = is_hacked
	pending_move = is_pending
	last_action = action
	queue_redraw()

func _process(delta: float) -> void:
	_phase += delta * (4.0 if hacked else 2.1)
	_flash = maxf(0.0, _flash - delta * 2.8)
	queue_redraw()

func animate_to(target: Vector2, duration: float, style: String = "move") -> void:
	pivot_offset = size / 2.0
	rotation = 0.0
	if duration <= 0.0:
		position = target
		scale = Vector2.ONE
		return

	var start_position: Vector2 = position
	var move_tween: Tween = create_tween()
	move_tween.set_ease(Tween.EASE_OUT)

	match style:
		"hop":
			var midpoint: Vector2 = start_position.lerp(target, 0.5) + Vector2(0.0, -size.y * 0.18)
			move_tween.set_trans(Tween.TRANS_SINE)
			move_tween.tween_property(self, "position", midpoint, duration * 0.5)
			move_tween.tween_property(self, "position", target, duration * 0.5)
			var jump_scale := create_tween()
			jump_scale.set_trans(Tween.TRANS_SINE)
			jump_scale.tween_property(self, "scale", Vector2(1.13, 1.13), duration * 0.5)
			jump_scale.tween_property(self, "scale", Vector2.ONE, duration * 0.5)
		"climb":
			var climb_mid: Vector2 = start_position.lerp(target, 0.5) + Vector2(0.0, -size.y * 0.10)
			move_tween.set_trans(Tween.TRANS_QUAD)
			move_tween.tween_property(self, "position", climb_mid, duration * 0.5)
			move_tween.tween_property(self, "position", target, duration * 0.5)
			var climb_tween := create_tween()
			climb_tween.tween_property(self, "rotation", deg_to_rad(-5.0), duration * 0.35)
			climb_tween.tween_property(self, "rotation", deg_to_rad(5.0), duration * 0.30)
			climb_tween.tween_property(self, "rotation", 0.0, duration * 0.35)
		"machine", "ride":
			move_tween.set_trans(Tween.TRANS_BACK)
			move_tween.tween_property(self, "position", target, duration)
			var machine_bump := create_tween()
			machine_bump.tween_property(self, "scale", Vector2(1.06, 0.96), duration * 0.35)
			machine_bump.tween_property(self, "scale", Vector2.ONE, duration * 0.65)
		"push":
			move_tween.set_trans(Tween.TRANS_QUAD)
			move_tween.tween_property(self, "position", target, duration)
			var push_tween := create_tween()
			push_tween.tween_property(self, "scale", Vector2(1.09, 0.93), duration * 0.35)
			push_tween.tween_property(self, "scale", Vector2.ONE, duration * 0.65)
		_:
			move_tween.set_trans(Tween.TRANS_QUAD)
			move_tween.tween_property(self, "position", target, duration)
			if entity_kind in ["F", "M"]:
				var step_tween := create_tween()
				step_tween.tween_property(self, "scale", Vector2(1.03, 0.97), duration * 0.45)
				step_tween.tween_property(self, "scale", Vector2.ONE, duration * 0.55)

func play_reaction(kind: String) -> void:
	pivot_offset = size / 2.0
	match kind:
		"hack":
			_flash = 1.0
			var tween := create_tween()
			tween.tween_property(self, "scale", Vector2(1.12, 1.12), 0.08)
			tween.tween_property(self, "scale", Vector2.ONE, 0.12)
		"rotate":
			var rotate_tween := create_tween()
			rotate_tween.tween_property(self, "rotation", deg_to_rad(8.0), 0.05)
			rotate_tween.tween_property(self, "rotation", deg_to_rad(-5.0), 0.05)
			rotate_tween.tween_property(self, "rotation", 0.0, 0.06)
		"blocked":
			var base: Vector2 = position
			var bump := create_tween()
			bump.tween_property(self, "position", base + Vector2(-3.0, 0.0), 0.035)
			bump.tween_property(self, "position", base + Vector2(3.0, 0.0), 0.035)
			bump.tween_property(self, "position", base, 0.035)
		_:
			pass

func fade_out_and_free(duration: float = 0.12) -> void:
	var tween: Tween = create_tween()
	tween.tween_property(self, "modulate:a", 0.0, duration)
	tween.parallel().tween_property(self, "scale", Vector2(0.72, 0.72), duration)
	tween.finished.connect(queue_free)

func _draw() -> void:
	var w: float = size.x
	var h: float = size.y
	var center: Vector2 = Vector2(w * 0.5, h * 0.5)
	var radius: float = minf(w, h) * 0.36
	var bob: float = 0.0
	if entity_kind in ["F", "M"] and last_action == "WAIT":
		bob = sin(_phase) * maxf(0.4, radius * 0.025)
	elif entity_kind in ["X", "G"] and pending_move:
		bob = sin(_phase * 1.6) * maxf(0.3, radius * 0.015)
	center.y += bob

	_draw_contact_shadow(center, radius)

	match entity_kind:
		"F":
			_draw_character_texture(IKOTOFOSA_TEXTURE, center, radius * 2.22, -radius * 0.02, false)
		"M":
			_draw_character_texture(IMAHAKI_TEXTURE, center, radius * 2.08, -radius * 0.02, true)
		"X":
			_draw_oriented_texture(EXCAVATOR_TEXTURE, center, radius * 2.45)
		"G":
			_draw_oriented_texture(GRAPPLER_TEXTURE, center, radius * 2.42)
		"C":
			_draw_texture_centered(CHEST_TEXTURE, center + Vector2(0.0, radius * 0.08), Vector2(radius * 2.05, radius * 1.82))
		_:
			draw_circle(center, radius, Color("#eeeeee"))

	if hacked and entity_kind in ["X", "G"]:
		var pulse: float = 1.0 + sin(_phase * 2.4) * 0.08
		draw_circle(center, radius * 1.15 * pulse, Color(0.18, 0.78, 1.0, 0.09))
		draw_arc(center, radius * 1.22 * pulse, 0.0, TAU, 36, Color("#45d8ff"), maxf(2.0, radius * 0.10))
		_draw_badge(center + Vector2(0.0, -radius * 0.96), "HACK", Color("#143a47"), Color("#8eeeff"))

	if _flash > 0.0:
		draw_circle(center, radius * (1.0 + _flash * 0.55), Color(0.55, 0.94, 1.0, _flash * 0.18))

	if pending_move and entity_kind in ["X", "G"]:
		_draw_badge(center + Vector2(radius * 0.72, radius * 0.83), "…", Color("#4c3817"), Color("#ffe08a"))

	if last_action.begins_with("PUSH_") and entity_kind in ["F", "M"]:
		_draw_badge(center + Vector2(0.0, radius * 0.95), "PUSH", Color("#4c2a14"), Color("#ffd08a"))

func _draw_character_texture(texture: Texture2D, center: Vector2, height: float, y_offset: float, narrow: bool) -> void:
	var aspect: float = float(texture.get_width()) / maxf(1.0, float(texture.get_height()))
	var width: float = height * aspect
	if narrow:
		width *= 0.93
	var horizontal_flip: float = -1.0 if facing == "LEFT" else 1.0
	draw_set_transform(center + Vector2(0.0, y_offset), 0.0, Vector2(horizontal_flip, 1.0))
	var rect: Rect2 = Rect2(Vector2(-width * 0.5, -height * 0.58), Vector2(width, height))
	draw_texture_rect(texture, rect, false)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

func _draw_oriented_texture(texture: Texture2D, center: Vector2, width: float) -> void:
	var aspect: float = float(texture.get_height()) / maxf(1.0, float(texture.get_width()))
	var height: float = width * aspect
	var angle: float = _orientation_angle(facing)
	draw_set_transform(center, angle, Vector2.ONE)
	var rect: Rect2 = Rect2(Vector2(-width * 0.5, -height * 0.5), Vector2(width, height))
	draw_texture_rect(texture, rect, false)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

func _draw_texture_centered(texture: Texture2D, center: Vector2, target_size: Vector2) -> void:
	var texture_aspect: float = float(texture.get_width()) / maxf(1.0, float(texture.get_height()))
	var wanted_aspect: float = target_size.x / maxf(1.0, target_size.y)
	var final_size: Vector2 = target_size
	if texture_aspect > wanted_aspect:
		final_size.y = target_size.x / texture_aspect
	else:
		final_size.x = target_size.y * texture_aspect
	var rect: Rect2 = Rect2(center - final_size * 0.5, final_size)
	draw_texture_rect(texture, rect, false)

func _orientation_angle(value: String) -> float:
	match value:
		"UP": return -PI * 0.5
		"DOWN": return PI * 0.5
		"LEFT": return PI
		_: return 0.0

func _draw_contact_shadow(center: Vector2, r: float) -> void:
	var points: PackedVector2Array = PackedVector2Array()
	for i in range(24):
		var angle: float = TAU * float(i) / 24.0
		points.append(center + Vector2(cos(angle) * r * 0.88, sin(angle) * r * 0.24) + Vector2(0.0, r * 0.68))
	draw_colored_polygon(points, Color(0.0, 0.0, 0.0, 0.24))

func _draw_badge(center: Vector2, text: String, background: Color, foreground: Color) -> void:
	if size.x < 24.0:
		return
	var font: Font = ThemeDB.fallback_font
	var font_size: int = maxi(7, int(size.x * 0.12))
	var badge_size: Vector2 = Vector2(maxf(size.x * 0.30, 34.0), maxf(size.y * 0.17, 18.0))
	draw_rect(Rect2(center - badge_size * 0.5, badge_size), background, true)
	draw_rect(Rect2(center - badge_size * 0.5, badge_size), foreground.darkened(0.55), false, 1.5)
	draw_string(font, center + Vector2(-badge_size.x * 0.5, font_size * 0.35), text, HORIZONTAL_ALIGNMENT_CENTER, badge_size.x, font_size, foreground)
