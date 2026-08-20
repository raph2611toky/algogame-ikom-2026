class_name OrbitCamera
extends Node3D

@export var yaw_degrees: float = 45.0
@export var pitch_degrees: float = -48.0
@export var orbit_sensitivity: float = 0.28
@export var pan_sensitivity: float = 0.0024
@export var keyboard_pan_speed: float = 12.0
@export var keyboard_rotate_speed: float = 70.0
@export var zoom_factor: float = 0.88

@onready var yaw_node: Node3D = $Yaw
@onready var pitch_node: Node3D = $Yaw/Pitch
@onready var camera: Camera3D = $Yaw/Pitch/Camera3D

var _distance: float = 22.0
var _default_distance: float = 22.0
var _fit_distance: float = 22.0
var _min_distance: float = 4.0
var _max_distance: float = 180.0
var _yaw: float = 0.0
var _pitch: float = 0.0
var _orbiting: bool = false
var _panning: bool = false
var _half_width: float = 8.0
var _half_depth: float = 8.0
var _center_y: float = 2.0

func _ready() -> void:
	_yaw = deg_to_rad(yaw_degrees)
	_pitch = deg_to_rad(pitch_degrees)
	_apply_camera()

func configure_for_board(world_width: float, world_depth: float, max_height: float, center_y: float) -> void:
	_half_width = maxf(2.0, world_width * 0.5)
	_half_depth = maxf(2.0, world_depth * 0.5)
	_center_y = center_y
	position = Vector3(0.0, _center_y, 0.0)

	var span: float = maxf(world_width, world_depth)
	var diagonal: float = Vector2(world_width, world_depth).length()
	_fit_distance = maxf(10.0, diagonal * 0.76 + max_height * 0.72)

	# Pour une grande carte, R garde des cases lisibles au lieu de miniaturiser tout le plan.
	var comfortable_span: float = minf(span, 34.0)
	_default_distance = maxf(10.0, comfortable_span * 0.88 + max_height * 0.58)
	_min_distance = maxf(4.0, minf(world_width, world_depth) * 0.12)
	_max_distance = maxf(_fit_distance * 2.5, 120.0)

	reset_view()

func reset_view() -> void:
	_yaw = deg_to_rad(yaw_degrees)
	_pitch = deg_to_rad(pitch_degrees)
	_distance = _default_distance
	position = Vector3(0.0, _center_y, 0.0)
	_apply_camera()

func fit_whole_board() -> void:
	position = Vector3(0.0, _center_y, 0.0)
	_distance = _fit_distance
	_apply_camera()

func _process(delta: float) -> void:
	var move := Vector2.ZERO
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		move.x -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		move.x += 1.0
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		move.y += 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		move.y -= 1.0

	if move.length_squared() > 0.0:
		move = move.normalized()
		_pan_world(move, keyboard_pan_speed * delta)

	if Input.is_key_pressed(KEY_Q):
		_yaw += deg_to_rad(keyboard_rotate_speed) * delta
		_apply_camera()
	if Input.is_key_pressed(KEY_E):
		_yaw -= deg_to_rad(keyboard_rotate_speed) * delta
		_apply_camera()

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index == MOUSE_BUTTON_RIGHT:
			_orbiting = mouse.pressed
			get_viewport().set_input_as_handled()
		elif mouse.button_index == MOUSE_BUTTON_MIDDLE or mouse.button_index == MOUSE_BUTTON_LEFT:
			_panning = mouse.pressed
			get_viewport().set_input_as_handled()
		elif mouse.pressed and mouse.button_index == MOUSE_BUTTON_WHEEL_UP:
			_distance = clampf(_distance * zoom_factor, _min_distance, _max_distance)
			_apply_camera()
			get_viewport().set_input_as_handled()
		elif mouse.pressed and mouse.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_distance = clampf(_distance / zoom_factor, _min_distance, _max_distance)
			_apply_camera()
			get_viewport().set_input_as_handled()

	elif event is InputEventMouseMotion:
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		if _orbiting:
			_yaw -= deg_to_rad(motion.relative.x * orbit_sensitivity)
			_pitch -= deg_to_rad(motion.relative.y * orbit_sensitivity)
			_pitch = clampf(_pitch, deg_to_rad(-85.0), deg_to_rad(-12.0))
			_apply_camera()
			get_viewport().set_input_as_handled()
		elif _panning:
			_pan_pixels(motion.relative)
			get_viewport().set_input_as_handled()

	elif event is InputEventKey:
		var key: InputEventKey = event as InputEventKey
		if key.pressed and not key.echo:
			if key.keycode == KEY_R or key.keycode == KEY_HOME:
				reset_view()
				get_viewport().set_input_as_handled()
			elif key.keycode == KEY_F:
				fit_whole_board()
				get_viewport().set_input_as_handled()

func _pan_pixels(relative: Vector2) -> void:
	var viewport_height: float = maxf(1.0, float(get_viewport().get_visible_rect().size.y))
	var world_per_pixel: float = (2.0 * _distance * tan(deg_to_rad(camera.fov) * 0.5)) / viewport_height
	var right: Vector3 = camera.global_transform.basis.x
	right.y = 0.0
	right = right.normalized()
	var forward: Vector3 = -camera.global_transform.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	position += (-right * relative.x + forward * relative.y) * world_per_pixel
	_clamp_target()

func _pan_world(axis: Vector2, amount: float) -> void:
	var right: Vector3 = camera.global_transform.basis.x
	right.y = 0.0
	right = right.normalized()
	var forward: Vector3 = -camera.global_transform.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	position += (right * axis.x + forward * axis.y) * amount
	_clamp_target()

func _clamp_target() -> void:
	# L'utilisateur peut légèrement dépasser le bord pour voir les faces externes.
	var margin_x: float = maxf(4.0, _half_width * 0.35)
	var margin_z: float = maxf(4.0, _half_depth * 0.35)
	position.x = clampf(position.x, -_half_width - margin_x, _half_width + margin_x)
	position.z = clampf(position.z, -_half_depth - margin_z, _half_depth + margin_z)
	position.y = _center_y
	_apply_camera()

func _apply_camera() -> void:
	yaw_node.rotation = Vector3(0.0, _yaw, 0.0)
	pitch_node.rotation = Vector3(_pitch, 0.0, 0.0)
	camera.position = Vector3(0.0, 0.0, _distance)
