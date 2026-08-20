class_name GameBoard
extends Control

const PREVIEW_SCENE: PackedScene = preload("res://scenes/tests/Plan3DPreview.tscn")

var state_ref: GameState
var visual_effects_strength: float = 1.0

var _viewport_container: SubViewportContainer
var _viewport: SubViewport
var _preview: Plan3DGenerator
var _last_layout_signature: int = 0

func _ready() -> void:
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_ALL
	_build_viewport()
	call_deferred("_resize_viewport")

func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and is_inside_tree():
		call_deferred("_resize_viewport")

func _build_viewport() -> void:
	if _viewport_container != null and is_instance_valid(_viewport_container):
		return

	_viewport_container = SubViewportContainer.new()
	_viewport_container.name = "Viewport3D"
	_viewport_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_viewport_container.stretch = true
	_viewport_container.stretch_shrink = 1
	add_child(_viewport_container)

	_viewport = SubViewport.new()
	_viewport.name = "BoardViewport"
	_viewport.transparent_bg = true
	_viewport.own_world_3d = true
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_viewport.msaa_3d = Viewport.MSAA_4X
	_viewport_container.add_child(_viewport)

	_preview = PREVIEW_SCENE.instantiate() as Plan3DGenerator
	_viewport.add_child(_preview)
	if _preview.has_node("UI"):
		_preview.get_node("UI").visible = false

func _resize_viewport() -> void:
	if _viewport == null:
		return
	var target := size
	if target.x <= 0.0 or target.y <= 0.0:
		target = Vector2(1280.0, 720.0)
	_viewport.size = Vector2i(target)

func set_effects_percent(percent: int) -> void:
	visual_effects_strength = clampf(float(percent) / 100.0, 0.0, 1.0)

func set_state(new_state: GameState, _events: Array = [], _animation_duration: float = 0.12) -> void:
	state_ref = new_state
	_build_viewport()
	if state_ref == null or _preview == null:
		return

	var display_grid: Array[String] = _compose_terrain_grid(state_ref)
	var layout_signature: int = hash("%d:%d:%s:%s" % [state_ref.width, state_ref.height, "|".join(PackedStringArray(display_grid)), str(state_ref.height_map)])
	var status: String = "PLAN 3D • %d × %d • tick %d • score %d" % [
		state_ref.width,
		state_ref.height,
		state_ref.tick,
		state_ref.score(),
	]

	if layout_signature != _last_layout_signature:
		_preview.load_runtime_data(display_grid, state_ref.height_map.duplicate(true), status)
		_last_layout_signature = layout_signature
	_preview.update_dynamic_state(state_ref, _animation_duration)

func get_render_summary() -> String:
	if state_ref == null:
		return "PLAN 3D INTÉGRÉ"
	return "PLAN 3D INTÉGRÉ • %d×%d • tick %d • score %d" % [
		state_ref.width,
		state_ref.height,
		state_ref.tick,
		state_ref.score(),
	]

func cell_center_local(pos: Vector2i) -> Vector2:
	if _preview == null or _preview.orbit_camera == null or _preview.orbit_camera.camera == null or _viewport == null:
		return size * 0.5
	var world_pos: Vector3 = _preview.get_cell_top_position(pos.y, pos.x)
	var projected: Vector2 = _preview.orbit_camera.camera.unproject_position(world_pos)
	var viewport_size := Vector2(_viewport.size)
	if viewport_size.x <= 0.0 or viewport_size.y <= 0.0:
		return size * 0.5
	return Vector2(projected.x * size.x / viewport_size.x, projected.y * size.y / viewport_size.y)

func reset_camera() -> void:
	if _preview != null and _preview.orbit_camera != null:
		_preview.orbit_camera.reset_view()

func center_camera_on_map() -> void:
	if _preview != null and _preview.orbit_camera != null:
		_preview.orbit_camera.fit_whole_board()

func _compose_terrain_grid(state: GameState) -> Array[String]:
	var rows: Array[String] = []
	for y: int in range(state.height):
		var chars: PackedStringArray = []
		for x: int in range(state.width):
			chars.append(str(state.terrain[y][x]))
		rows.append("".join(chars))
	return rows
