extends Node3D

const PAIR_LOADER = preload("res://scripts/game/map_elevation_pair_loader.gd")
const TERRAIN_FACTORY = preload("res://scripts/game/terrain/terraced_plan_mesh_factory.gd")
const TOP_TEXTURE: Texture2D = preload("res://assets/game/terrain/plan_top.svg")
const SLOPE_TEXTURE: Texture2D = preload("res://assets/game/terrain/plan_slope.svg")

@export_file("*.txt") var map_path := "res://data/plan_demo/map.txt"
@export_file("*.txt") var elevation_path := "res://data/plan_demo/elevation.txt"

# Géométrie visuelle. Une case logique reste grande et lisible.
const CELL_SIZE := 3.15
const BASE_HEIGHT := 0.42
const LEVEL_HEIGHT := 0.72
const TRANSITION_RATIO := 0.42
const OUTER_SLOPE_RATIO := 0.88

# Caméra orbitale.
const DEFAULT_YAW := deg_to_rad(45.0)
const DEFAULT_PITCH := deg_to_rad(52.0)
const MIN_PITCH := deg_to_rad(12.0)
const MAX_PITCH := deg_to_rad(82.0)
const ORBIT_SENSITIVITY := 0.008
const ROTATE_KEY_SPEED := 1.15
const PAN_KEY_SPEED := 0.72
const ZOOM_FACTOR := 0.88

@onready var terrain_root: Node3D = $Terrain
@onready var collision_root: StaticBody3D = $TerrainCollision
@onready var camera: Camera3D = $Camera3D
@onready var status: Label = $UI/Status
@onready var help_label: Label = $UI/Help

var data: Dictionary = {}
var terrain_mesh: ArrayMesh
var orbit_target := Vector3.ZERO
var yaw := DEFAULT_YAW
var pitch := DEFAULT_PITCH
var distance := 24.0
var default_distance := 24.0
var min_distance := 4.0
var max_distance := 160.0
var fit_distance := 24.0
var orbiting := false
var panning := false

func _ready() -> void:
	var result: Dictionary = PAIR_LOADER.load_pair(map_path, elevation_path)
	if not bool(result.get("ok", false)):
		status.text = "ERREUR : %s" % str(result.get("error", "Erreur inconnue"))
		push_error(status.text)
		return
	data = result["data"]
	_build_plan()
	_reset_camera(true)
	status.text = "PLAN 3D STYLISÉ V2  •  %d × %d  •  élévations 1 → %d" % [int(data["height"]), int(data["width"]), int(data["max_elevation"])]
	help_label.text = "Clic droit + glisser : tourner   •   Clic gauche/milieu + glisser : déplacer   •   Molette : zoom\nWASD / flèches : parcourir   •   Q / E : pivoter   •   R : vue isométrique   •   F : cadrer toute la carte"

func _process(delta: float) -> void:
	if data.is_empty():
		return
	var changed := false

	var x_axis := 0.0
	var z_axis := 0.0
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		x_axis -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		x_axis += 1.0
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		z_axis += 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		z_axis -= 1.0

	if not is_zero_approx(x_axis) or not is_zero_approx(z_axis):
		_pan_world(Vector2(x_axis, z_axis), delta)
		changed = true

	if Input.is_key_pressed(KEY_Q):
		yaw += ROTATE_KEY_SPEED * delta
		changed = true
	if Input.is_key_pressed(KEY_E):
		yaw -= ROTATE_KEY_SPEED * delta
		changed = true

	if changed:
		_update_camera()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse := event as InputEventMouseButton
		if mouse.button_index == MOUSE_BUTTON_RIGHT:
			orbiting = mouse.pressed
			get_viewport().set_input_as_handled()
		elif mouse.button_index == MOUSE_BUTTON_MIDDLE or mouse.button_index == MOUSE_BUTTON_LEFT:
			panning = mouse.pressed
			get_viewport().set_input_as_handled()
		elif mouse.pressed and mouse.button_index == MOUSE_BUTTON_WHEEL_UP:
			_zoom(ZOOM_FACTOR)
			get_viewport().set_input_as_handled()
		elif mouse.pressed and mouse.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_zoom(1.0 / ZOOM_FACTOR)
			get_viewport().set_input_as_handled()

	elif event is InputEventMouseMotion:
		var motion := event as InputEventMouseMotion
		if orbiting:
			yaw -= motion.relative.x * ORBIT_SENSITIVITY
			pitch = clampf(pitch + motion.relative.y * ORBIT_SENSITIVITY, MIN_PITCH, MAX_PITCH)
			_update_camera()
			get_viewport().set_input_as_handled()
		elif panning:
			_pan_pixels(motion.relative)
			_update_camera()
			get_viewport().set_input_as_handled()

	elif event is InputEventKey and event.pressed and not event.echo:
		var key := event as InputEventKey
		if key.keycode == KEY_R or key.keycode == KEY_HOME:
			_reset_camera(true)
			get_viewport().set_input_as_handled()
		elif key.keycode == KEY_F:
			_fit_whole_map()
			get_viewport().set_input_as_handled()

func _build_plan() -> void:
	for child in terrain_root.get_children():
		child.queue_free()
	for child in collision_root.get_children():
		child.queue_free()

	var rows: int = int(data["height"])
	var cols: int = int(data["width"])
	var heights: Array = data["height_map"]
	var total_cells := rows * cols
	var subdivisions: int = TERRAIN_FACTORY.recommended_subdivisions(total_cells)

	var material := _create_terrain_material()
	terrain_mesh = TERRAIN_FACTORY.create_plan_mesh(
		heights,
		CELL_SIZE,
		BASE_HEIGHT,
		LEVEL_HEIGHT,
		TRANSITION_RATIO,
		OUTER_SLOPE_RATIO,
		material,
		subdivisions
	)

	var terrain := MeshInstance3D.new()
	terrain.name = "ContinuousTerracedPlan"
	terrain.mesh = terrain_mesh
	terrain.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	terrain_root.add_child(terrain)

	# Une seule collision pour le relief complet : pas de fentes entre les cases.
	var collision := CollisionShape3D.new()
	collision.name = "ContinuousTerrainCollision"
	collision.shape = terrain_mesh.create_trimesh_shape()
	collision_root.add_child(collision)

func _create_terrain_material() -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = """
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

uniform sampler2D top_tex : source_color, repeat_enable, filter_linear_mipmap_anisotropic;
uniform sampler2D slope_tex : source_color, repeat_enable, filter_linear_mipmap_anisotropic;
uniform vec3 top_tint = vec3(1.0, 0.96, 0.86);
uniform vec3 slope_tint = vec3(0.84, 0.68, 0.50);
uniform float top_scale = 1.0;

void fragment() {
    vec3 top_color = texture(top_tex, UV * top_scale).rgb * top_tint;
    vec3 stone_color = texture(slope_tex, UV * vec2(1.25, 2.0)).rgb * slope_tint;

    // NORMAL est en espace vue dans le fragment shader. On le reconvertit en
    // espace monde pour que la texture des pentes ne change pas quand la caméra tourne.
    vec3 world_normal = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
    float flatness = smoothstep(0.82, 0.975, clamp(world_normal.y, 0.0, 1.0));
    vec3 color = mix(stone_color, top_color, flatness);

    // Très légère accentuation des faces orientées vers le bas de la lumière :
    // donne du volume sans couleurs arc-en-ciel par altitude.
    float relief = mix(0.90, 1.04, clamp(world_normal.y, 0.0, 1.0));
    ALBEDO = color * relief;
    // Une faible émission garantit que le relief reste lisible même si une
    // configuration de lumière du GPU diffère de la prévisualisation.
    EMISSION = color * 0.12;
    ROUGHNESS = mix(0.98, 0.88, flatness);
    METALLIC = 0.0;
}
"""
	var material := ShaderMaterial.new()
	material.shader = shader
	material.set_shader_parameter("top_tex", TOP_TEXTURE)
	material.set_shader_parameter("slope_tex", SLOPE_TEXTURE)
	material.set_shader_parameter("top_tint", Vector3(1.0, 0.96, 0.87))
	material.set_shader_parameter("slope_tint", Vector3(0.88, 0.72, 0.54))
	material.set_shader_parameter("top_scale", 1.0)
	return material

func _reset_camera(fit_map: bool) -> void:
	yaw = DEFAULT_YAW
	pitch = DEFAULT_PITCH
	orbit_target = Vector3(0.0, _terrain_mid_height(), 0.0)
	_recalculate_camera_limits()
	if fit_map:
		distance = default_distance
	_update_camera()

func _fit_whole_map() -> void:
	orbit_target = Vector3(0.0, _terrain_mid_height(), 0.0)
	distance = fit_distance
	_update_camera()

func _recalculate_camera_limits() -> void:
	var rows: int = int(data["height"])
	var cols: int = int(data["width"])
	var world_w: float = float(cols) * CELL_SIZE + CELL_SIZE * OUTER_SLOPE_RATIO * 2.0
	var world_d: float = float(rows) * CELL_SIZE + CELL_SIZE * OUTER_SLOPE_RATIO * 2.0
	var span: float = maxf(world_w, world_d)
	var peak: float = _terrain_peak_height()

	# F = cadrage complet. R = vue confortable. Ainsi une future grande map
	# n'est pas miniaturisée au démarrage : on la parcourt avec la caméra.
	fit_distance = maxf(10.0, span * 0.98 + peak * 0.55)
	var comfortable_span: float = minf(span, CELL_SIZE * 13.0)
	default_distance = maxf(10.0, comfortable_span * 0.82 + peak * 0.45)
	min_distance = maxf(3.5, CELL_SIZE * 1.65)
	max_distance = maxf(fit_distance * 2.5, 80.0)

func _update_camera() -> void:
	var horizontal := cos(pitch)
	var offset := Vector3(
		sin(yaw) * horizontal,
		sin(pitch),
		cos(yaw) * horizontal
	) * distance
	camera.global_position = orbit_target + offset
	camera.look_at(orbit_target, Vector3.UP)

func _zoom(factor: float) -> void:
	distance = clampf(distance * factor, min_distance, max_distance)
	_update_camera()

func _pan_pixels(relative: Vector2) -> void:
	var viewport_height := maxf(1.0, float(get_viewport().get_visible_rect().size.y))
	var world_per_pixel := (2.0 * distance * tan(deg_to_rad(camera.fov) * 0.5)) / viewport_height
	var right := camera.global_transform.basis.x
	right.y = 0.0
	right = right.normalized()
	var forward := -camera.global_transform.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	orbit_target += (-right * relative.x + forward * relative.y) * world_per_pixel
	_clamp_target_to_map()

func _pan_world(axis: Vector2, delta: float) -> void:
	var right := camera.global_transform.basis.x
	right.y = 0.0
	right = right.normalized()
	var forward := -camera.global_transform.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	var speed := maxf(CELL_SIZE * 1.8, distance * PAN_KEY_SPEED)
	orbit_target += (right * axis.x + forward * axis.y) * speed * delta
	_clamp_target_to_map()

func _clamp_target_to_map() -> void:
	var cols: int = int(data.get("width", 1))
	var rows: int = int(data.get("height", 1))
	var half_w: float = maxf(CELL_SIZE, float(cols - 1) * CELL_SIZE * 0.5 + CELL_SIZE)
	var half_d: float = maxf(CELL_SIZE, float(rows - 1) * CELL_SIZE * 0.5 + CELL_SIZE)
	orbit_target.x = clampf(orbit_target.x, -half_w, half_w)
	orbit_target.z = clampf(orbit_target.z, -half_d, half_d)

func _terrain_peak_height() -> float:
	var max_level := maxi(1, int(data.get("max_elevation", 1)))
	return BASE_HEIGHT + float(max_level - 1) * LEVEL_HEIGHT

func _terrain_mid_height() -> float:
	if data.is_empty():
		return _terrain_peak_height() * 0.42
	var heights: Array = data.get("height_map", []) as Array
	var total: float = 0.0
	var count: int = 0
	for source_row in heights:
		var row: Array = source_row as Array
		for value in row:
			var level: int = int(value)
			if level > 0:
				total += BASE_HEIGHT + float(level - 1) * LEVEL_HEIGHT
				count += 1
	if count <= 0:
		return _terrain_peak_height() * 0.42
	return total / float(count)
