class_name Plan3DGenerator
extends Node3D

const ElevationLoaderScript = preload("res://scripts/plan3d/elevation_loader.gd")

@export_file("*.txt") var map_path: String = "res://data/plan_demo/map.txt"
@export_file("*.txt") var elevation_path: String = "res://data/plan_demo/elevation.txt"

@export_group("Geometry")
@export var cell_size: float = 2.85
@export var level_height: float = 0.78
@export_range(0.00, 0.10, 0.005) var tile_gap_ratio: float = 0.012
@export_range(0.04, 0.30, 0.01) var rim_width: float = 0.14
@export_range(0.02, 0.18, 0.01) var rim_drop: float = 0.07
@export_range(0.08, 0.45, 0.01) var slope_run_ratio: float = 0.24
@export_range(0.00, 0.20, 0.01) var slope_extra_per_level: float = 0.035
@export_range(0.005, 0.12, 0.001) var seam_half_size: float = 0.060
@export_range(0.00, 0.08, 0.001) var seam_overlap: float = 0.026
@export_range(0.30, 0.72, 0.01) var hole_opening_ratio: float = 0.68
@export_range(0.05, 0.30, 0.01) var hole_inner_bevel_width: float = 0.06
@export_range(0.15, 0.90, 0.01) var hole_depth: float = 0.82

@export_group("Style")
@export var top_tint: Color = Color("e8d2a3")
@export var rim_tint: Color = Color("c7a270")
@export var slope_tint: Color = Color("865d3d")
@export var top_emission_strength: float = 0.055

@onready var terrain: MeshInstance3D = $Terrain
@onready var terrain_collision: CollisionShape3D = $TerrainBody/TerrainCollision
@onready var orbit_camera: OrbitCamera = $CameraRig
@onready var props: Plan3DPropSpawner = $Props
@onready var status_label: Label = $UI/Status

var _height_map: Array = []
var _map_grid: Array[String] = []
var _rows: int = 0
var _cols: int = 0
var _runtime_loaded: bool = false
var _camera_configured: bool = false


func _ready() -> void:
	if _runtime_loaded:
		_rebuild_from_current_data()
		return
	var result: Dictionary = ElevationLoaderScript.load_pair(map_path, elevation_path)
	if not bool(result.get("ok", false)):
		var message: String = str(result.get("error", "Erreur inconnue"))
		status_label.text = "ERREUR • %s" % message
		push_error(message)
		return

	var data: Dictionary = result["data"] as Dictionary
	_map_grid.clear()
	for row_value: Variant in data["grid"]:
		_map_grid.append(str(row_value))
	_rows = int(data["height"])
	_cols = int(data["width"])
	_height_map = _resolve_rock_heights(data["height_map"] as Array)
	_rebuild_from_current_data()


func load_runtime_data(map_grid: Array, height_map: Array, status_text: String = "") -> void:
	_runtime_loaded = true
	_map_grid.clear()
	for row_value: Variant in map_grid:
		_map_grid.append(str(row_value))
	_rows = _map_grid.size()
	_cols = 0 if _rows == 0 else _map_grid[0].length()
	_height_map = _resolve_rock_heights(height_map)
	if is_node_ready():
		_rebuild_from_current_data(status_text)
	else:
		call_deferred("_rebuild_from_current_data", status_text)


func refresh_runtime_grid(map_grid: Array, status_text: String = "") -> void:
	_runtime_loaded = true
	_map_grid.clear()
	for row_value: Variant in map_grid:
		_map_grid.append(str(row_value))
	_rows = _map_grid.size()
	_cols = 0 if _rows == 0 else _map_grid[0].length()
	if is_node_ready():
		props.populate_static(_map_grid, self)
		_update_status_text(status_text)
	else:
		call_deferred("refresh_runtime_grid", map_grid, status_text)


func _rebuild_from_current_data(status_text: String = "") -> void:
	if terrain == null or terrain_collision == null or props == null or orbit_camera == null:
		return
	if _rows <= 0 or _cols <= 0:
		return
	var board_mesh: ArrayMesh = _build_board_mesh()
	terrain.mesh = board_mesh
	terrain.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	terrain_collision.shape = board_mesh.create_trimesh_shape()
	props.populate_static(_map_grid, self)
	if not _camera_configured:
		var world_width: float = float(_cols) * cell_size
		var world_depth: float = float(_rows) * cell_size
		var max_level: int = _max_level()
		var max_height: float = float(max_level) * level_height
		var average_height: float = _average_height() * level_height
		orbit_camera.configure_for_board(world_width, world_depth, max_height, average_height * 0.55)
		_camera_configured = true
	_update_status_text(status_text)


func _update_status_text(status_text: String = "") -> void:
	if status_label == null:
		return
	if not status_text.is_empty():
		status_label.text = status_text
		return
	status_label.text = "PLAN 3D • %d × %d • élévations %d → %d" % [
		_rows,
		_cols,
		_min_level(),
		_max_level(),
	]


func _min_level() -> int:
	var best: int = 9
	for row_value: Variant in _height_map:
		var row: Array = row_value as Array
		for value: Variant in row:
			best = mini(best, clampi(int(value), 1, 9))
	return best


func _max_level() -> int:
	var best: int = 1
	for row_value: Variant in _height_map:
		var row: Array = row_value as Array
		for value: Variant in row:
			best = maxi(best, clampi(int(value), 1, 9))
	return best


func _build_board_mesh() -> ArrayMesh:
	var mesh := ArrayMesh.new()

	var top_st := SurfaceTool.new()
	top_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_build_top_faces(top_st)
	top_st.index()
	top_st.commit(mesh)
	mesh.surface_set_material(0, _make_top_material())

	var rim_st := SurfaceTool.new()
	rim_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_build_rim_faces(rim_st)
	rim_st.index()
	rim_st.commit(mesh)
	mesh.surface_set_material(1, _make_rim_material())

	var fill_st := SurfaceTool.new()
	fill_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_build_underfill_columns(fill_st)
	_build_hole_interiors(fill_st)
	fill_st.index()
	fill_st.commit(mesh)
	mesh.surface_set_material(2, _make_fill_material())

	var slope_st := SurfaceTool.new()
	slope_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_build_slope_faces(slope_st)
	_build_corner_seam_faces(slope_st)
	slope_st.index()
	slope_st.commit(mesh)
	mesh.surface_set_material(3, _make_slope_material())

	return mesh


# -----------------------------------------------------------------------------
# FLAT CELL TOPS
# -----------------------------------------------------------------------------

func _build_top_faces(st: SurfaceTool) -> void:
	var half: float = cell_size * 0.5
	var gap: float = cell_size * tile_gap_ratio
	var outer_half: float = half - gap * 0.5
	var inner_half: float = maxf(outer_half - rim_width, cell_size * 0.30)

	for r: int in range(_rows):
		for c: int in range(_cols):
			var y: float = _cell_top_y(r, c)
			var center: Vector3 = _cell_center(r, c)
			if _is_hole_cell(r, c):
				_add_hole_top_ring(st, center, y, inner_half)
			else:
				_add_horizontal_quad(
					st,
					Vector3(center.x - inner_half, y, center.z - inner_half),
					Vector3(center.x + inner_half, y, center.z - inner_half),
					Vector3(center.x + inner_half, y, center.z + inner_half),
					Vector3(center.x - inner_half, y, center.z + inner_half)
				)


# -----------------------------------------------------------------------------
# SMALL BEVEL AROUND EVERY TILE TOP
# -----------------------------------------------------------------------------

func _build_rim_faces(st: SurfaceTool) -> void:
	var half: float = cell_size * 0.5
	var gap: float = cell_size * tile_gap_ratio
	var outer_half: float = half - gap * 0.5
	var inner_half: float = maxf(outer_half - rim_width, cell_size * 0.30)

	for r: int in range(_rows):
		for c: int in range(_cols):
			var y_top: float = _cell_top_y(r, c)
			var y_edge: float = y_top - rim_drop
			var center: Vector3 = _cell_center(r, c)

			# North
			_add_quad(
				st,
				Vector3(center.x - inner_half, y_top, center.z - inner_half),
				Vector3(center.x + inner_half, y_top, center.z - inner_half),
				Vector3(center.x + outer_half, y_edge, center.z - outer_half),
				Vector3(center.x - outer_half, y_edge, center.z - outer_half),
				Vector3(0.0, 0.86, -0.50)
			)

			# South
			_add_quad(
				st,
				Vector3(center.x + inner_half, y_top, center.z + inner_half),
				Vector3(center.x - inner_half, y_top, center.z + inner_half),
				Vector3(center.x - outer_half, y_edge, center.z + outer_half),
				Vector3(center.x + outer_half, y_edge, center.z + outer_half),
				Vector3(0.0, 0.86, 0.50)
			)

			# West
			_add_quad(
				st,
				Vector3(center.x - inner_half, y_top, center.z + inner_half),
				Vector3(center.x - inner_half, y_top, center.z - inner_half),
				Vector3(center.x - outer_half, y_edge, center.z - outer_half),
				Vector3(center.x - outer_half, y_edge, center.z + outer_half),
				Vector3(-0.50, 0.86, 0.0)
			)

			# East
			_add_quad(
				st,
				Vector3(center.x + inner_half, y_top, center.z - inner_half),
				Vector3(center.x + inner_half, y_top, center.z + inner_half),
				Vector3(center.x + outer_half, y_edge, center.z + outer_half),
				Vector3(center.x + outer_half, y_edge, center.z - outer_half),
				Vector3(0.50, 0.86, 0.0)
			)

			if _is_hole_cell(r, c):
				_add_hole_inner_bevel(st, center, y_top)


# -----------------------------------------------------------------------------
# SLOPED TERRACE SIDES
# The old version made vertical walls. Here, the upper edge stays under the
# flat tile and the lower edge is shifted OUTWARD toward the lower neighbour.
# This gives the exact trapezoidal hillside profile requested.
# -----------------------------------------------------------------------------

func _build_slope_faces(st: SurfaceTool) -> void:
	var half: float = cell_size * 0.5
	var gap: float = cell_size * tile_gap_ratio
	var edge: float = half - gap * 0.5

	for r: int in range(_rows):
		for c: int in range(_cols):
			var high_level: int = _level_at(r, c)
			var center: Vector3 = _cell_center(r, c)

			var north_level: int = _level_at_or_zero(r - 1, c)
			var south_level: int = _level_at_or_zero(r + 1, c)
			var west_level: int = _level_at_or_zero(r, c - 1)
			var east_level: int = _level_at_or_zero(r, c + 1)

			_add_slope_if_needed(st, center, high_level, north_level, Vector3(0.0, 0.0, -1.0), edge)
			_add_slope_if_needed(st, center, high_level, south_level, Vector3(0.0, 0.0, 1.0), edge)
			_add_slope_if_needed(st, center, high_level, west_level, Vector3(-1.0, 0.0, 0.0), edge)
			_add_slope_if_needed(st, center, high_level, east_level, Vector3(1.0, 0.0, 0.0), edge)

			# Fill the tiny triangular openings visible at terrace corners when two
			# neighbouring sides are both lower than the current cell.
			_add_corner_fill_if_needed(st, center, high_level, north_level, west_level, Vector2(-1.0, -1.0), edge)
			_add_corner_fill_if_needed(st, center, high_level, north_level, east_level, Vector2(1.0, -1.0), edge)
			_add_corner_fill_if_needed(st, center, high_level, south_level, west_level, Vector2(-1.0, 1.0), edge)
			_add_corner_fill_if_needed(st, center, high_level, south_level, east_level, Vector2(1.0, 1.0), edge)


func _add_slope_if_needed(
	st: SurfaceTool,
	center: Vector3,
	high_level: int,
	low_level: int,
	direction: Vector3,
	edge: float
) -> void:
	if low_level >= high_level:
		return

	var difference: int = high_level - low_level
	var top_y: float = float(high_level) * level_height - rim_drop
	var bottom_y: float = float(low_level) * level_height - 0.012

	# A larger altitude difference gives a slightly wider foot, but never enough
	# to swallow the lower cell. This preserves the clear square-cell layout.
	var run: float = _compute_slope_run(difference)

	# Occupy the full side width so adjacent side faces meet cleanly at corners.
	var side_half: float = edge + 0.040
	var rise: float = maxf(0.001, top_y - bottom_y)
	var normal: Vector3 = Vector3(direction.x * rise, run, direction.z * rise).normalized()

	if direction.z < 0.0:
		_add_quad(
			st,
			Vector3(center.x - side_half, top_y, center.z - edge),
			Vector3(center.x + side_half, top_y, center.z - edge),
			Vector3(center.x + side_half, bottom_y, center.z - edge - run),
			Vector3(center.x - side_half, bottom_y, center.z - edge - run),
			normal
		)
	elif direction.z > 0.0:
		_add_quad(
			st,
			Vector3(center.x + side_half, top_y, center.z + edge),
			Vector3(center.x - side_half, top_y, center.z + edge),
			Vector3(center.x - side_half, bottom_y, center.z + edge + run),
			Vector3(center.x + side_half, bottom_y, center.z + edge + run),
			normal
		)
	elif direction.x < 0.0:
		_add_quad(
			st,
			Vector3(center.x - edge, top_y, center.z + side_half),
			Vector3(center.x - edge, top_y, center.z - side_half),
			Vector3(center.x - edge - run, bottom_y, center.z - side_half),
			Vector3(center.x - edge - run, bottom_y, center.z + side_half),
			normal
		)
	else:
		_add_quad(
			st,
			Vector3(center.x + edge, top_y, center.z - side_half),
			Vector3(center.x + edge, top_y, center.z + side_half),
			Vector3(center.x + edge + run, bottom_y, center.z + side_half),
			Vector3(center.x + edge + run, bottom_y, center.z - side_half),
			normal
		)


func _add_corner_fill_if_needed(
	st: SurfaceTool,
	center: Vector3,
	high_level: int,
	first_low_level: int,
	second_low_level: int,
	corner_sign: Vector2,
	edge: float
) -> void:
	if first_low_level >= high_level or second_low_level >= high_level:
		return

	var top_y: float = float(high_level) * level_height - rim_drop
	var first_difference: int = high_level - first_low_level
	var second_difference: int = high_level - second_low_level
	var first_bottom_y: float = float(first_low_level) * level_height - 0.012
	var second_bottom_y: float = float(second_low_level) * level_height - 0.012
	var first_run: float = _compute_slope_run(first_difference)
	var second_run: float = _compute_slope_run(second_difference)

	var top_corner := Vector3(
		center.x + edge * corner_sign.x,
		top_y,
		center.z + edge * corner_sign.y
	)

	var first_bottom: Vector3
	var second_bottom: Vector3

	if absf(corner_sign.x) > 0.0 and absf(corner_sign.y) > 0.0:
		# first_low_level is the Z side (north/south), second_low_level is the X side (west/east)
		first_bottom = Vector3(
			top_corner.x,
			first_bottom_y,
			top_corner.z + first_run * corner_sign.y
		)
		second_bottom = Vector3(
			top_corner.x + second_run * corner_sign.x,
			second_bottom_y,
			top_corner.z
		)

	var edge_a: Vector3 = first_bottom - top_corner
	var edge_b: Vector3 = second_bottom - top_corner
	var normal: Vector3 = edge_b.cross(edge_a).normalized()
	if normal.y < 0.0:
		normal = -normal

	_add_triangle(st, top_corner, first_bottom, second_bottom, normal)


func _compute_slope_run(difference: int) -> float:
	var base_run: float = cell_size * slope_run_ratio
	var extra_run: float = cell_size * slope_extra_per_level * float(maxi(0, difference - 1))
	return minf(base_run + extra_run, cell_size * 0.38)


# -----------------------------------------------------------------------------
# CORNER SEAM FILL
# Add a tiny filler column at every grid vertex to hide residual holes where
# multiple trapezoidal side faces meet. The piece is intentionally very small
# and uses the same slope material so it visually disappears while removing
# the black spacing artifact.
# -----------------------------------------------------------------------------

func _build_corner_seam_faces(st: SurfaceTool) -> void:
	if _rows <= 1 or _cols <= 1:
		return

	var half: float = seam_half_size
	for r: int in range(_rows - 1):
		for c: int in range(_cols - 1):
			var nw_level: int = _level_at(r, c)
			var ne_level: int = _level_at(r, c + 1)
			var sw_level: int = _level_at(r + 1, c)
			var se_level: int = _level_at(r + 1, c + 1)

			var top_level: int = maxi(maxi(nw_level, ne_level), maxi(sw_level, se_level))
			var bottom_level: int = mini(mini(nw_level, ne_level), mini(sw_level, se_level))
			if top_level <= bottom_level:
				continue

			var vertex_x: float = (_cell_center(r, c).x + _cell_center(r, c + 1).x) * 0.5
			var vertex_z: float = (_cell_center(r, c).z + _cell_center(r + 1, c).z) * 0.5
			var top_y: float = float(top_level) * level_height - rim_drop + seam_overlap * 1.4
			var bottom_y: float = float(bottom_level) * level_height - 0.018
			if bottom_y >= top_y:
				continue

			var p000 := Vector3(vertex_x - half, bottom_y, vertex_z - half)
			var p100 := Vector3(vertex_x + half, bottom_y, vertex_z - half)
			var p110 := Vector3(vertex_x + half, bottom_y, vertex_z + half)
			var p010 := Vector3(vertex_x - half, bottom_y, vertex_z + half)
			var p001 := Vector3(vertex_x - half, top_y, vertex_z - half)
			var p101 := Vector3(vertex_x + half, top_y, vertex_z - half)
			var p111 := Vector3(vertex_x + half, top_y, vertex_z + half)
			var p011 := Vector3(vertex_x - half, top_y, vertex_z + half)

			_add_quad(st, p001, p101, p100, p000, Vector3(0.0, 0.0, -1.0))
			_add_quad(st, p011, p010, p110, p111, Vector3(0.0, 0.0, 1.0))
			_add_quad(st, p001, p000, p010, p011, Vector3(-1.0, 0.0, 0.0))
			_add_quad(st, p101, p111, p110, p100, Vector3(1.0, 0.0, 0.0))



func _is_hole_cell(r: int, c: int) -> bool:
	if r < 0 or r >= _map_grid.size():
		return false
	var row: String = _map_grid[r]
	if c < 0 or c >= row.length():
		return false
	return row.substr(c, 1) == "o"


func _hole_half_size() -> float:
	return cell_size * hole_opening_ratio * 0.5


func _add_hole_top_ring(st: SurfaceTool, center: Vector3, y: float, outer_half: float) -> void:
	# Same surface/material as every normal tile. Only the center is omitted.
	var hole_half: float = minf(_hole_half_size(), outer_half - rim_width * 1.25)
	var x0: float = center.x - outer_half
	var x1: float = center.x - hole_half
	var x2: float = center.x + hole_half
	var x3: float = center.x + outer_half
	var z0: float = center.z - outer_half
	var z1: float = center.z - hole_half
	var z2: float = center.z + hole_half
	var z3: float = center.z + outer_half

	# North strip
	_add_horizontal_quad(st, Vector3(x0,y,z0), Vector3(x3,y,z0), Vector3(x3,y,z1), Vector3(x0,y,z1))
	# South strip
	_add_horizontal_quad(st, Vector3(x0,y,z2), Vector3(x3,y,z2), Vector3(x3,y,z3), Vector3(x0,y,z3))
	# West strip
	_add_horizontal_quad(st, Vector3(x0,y,z1), Vector3(x1,y,z1), Vector3(x1,y,z2), Vector3(x0,y,z2))
	# East strip
	_add_horizontal_quad(st, Vector3(x2,y,z1), Vector3(x3,y,z1), Vector3(x3,y,z2), Vector3(x2,y,z2))


func _add_hole_inner_bevel(st: SurfaceTool, center: Vector3, y_top: float) -> void:
	var hole_half: float = _hole_half_size()
	var bevel: float = minf(hole_inner_bevel_width, hole_half * 0.35)
	var inner: float = maxf(0.05, hole_half - bevel)
	var y_inner: float = y_top - rim_drop * 0.80

	# North inner lip
	_add_quad(st,
		Vector3(center.x - hole_half, y_top, center.z - hole_half),
		Vector3(center.x + hole_half, y_top, center.z - hole_half),
		Vector3(center.x + inner, y_inner, center.z - inner),
		Vector3(center.x - inner, y_inner, center.z - inner),
		Vector3(0.0, 0.75, 0.65))
	# South inner lip
	_add_quad(st,
		Vector3(center.x + hole_half, y_top, center.z + hole_half),
		Vector3(center.x - hole_half, y_top, center.z + hole_half),
		Vector3(center.x - inner, y_inner, center.z + inner),
		Vector3(center.x + inner, y_inner, center.z + inner),
		Vector3(0.0, 0.75, -0.65))
	# West inner lip
	_add_quad(st,
		Vector3(center.x - hole_half, y_top, center.z + hole_half),
		Vector3(center.x - hole_half, y_top, center.z - hole_half),
		Vector3(center.x - inner, y_inner, center.z - inner),
		Vector3(center.x - inner, y_inner, center.z + inner),
		Vector3(0.65, 0.75, 0.0))
	# East inner lip
	_add_quad(st,
		Vector3(center.x + hole_half, y_top, center.z - hole_half),
		Vector3(center.x + hole_half, y_top, center.z + hole_half),
		Vector3(center.x + inner, y_inner, center.z + inner),
		Vector3(center.x + inner, y_inner, center.z - inner),
		Vector3(-0.65, 0.75, 0.0))


func _build_hole_interiors(st: SurfaceTool) -> void:
	for r: int in range(_rows):
		for c: int in range(_cols):
			if not _is_hole_cell(r, c):
				continue
			var center: Vector3 = _cell_center(r, c)
			var top_y: float = _cell_top_y(r, c) - rim_drop * 0.80
			var bottom_y: float = maxf(0.02, top_y - hole_depth)
			var hole_half: float = maxf(0.05, _hole_half_size() - hole_inner_bevel_width)
			var bottom_half: float = hole_half * 0.82

			# Four inward-tapered dirt/stone walls.
			_add_quad(st,
				Vector3(center.x - hole_half, top_y, center.z - hole_half),
				Vector3(center.x + hole_half, top_y, center.z - hole_half),
				Vector3(center.x + bottom_half, bottom_y, center.z - bottom_half),
				Vector3(center.x - bottom_half, bottom_y, center.z - bottom_half),
				Vector3(0.0, 0.15, 0.99))
			_add_quad(st,
				Vector3(center.x + hole_half, top_y, center.z + hole_half),
				Vector3(center.x - hole_half, top_y, center.z + hole_half),
				Vector3(center.x - bottom_half, bottom_y, center.z + bottom_half),
				Vector3(center.x + bottom_half, bottom_y, center.z + bottom_half),
				Vector3(0.0, 0.15, -0.99))
			_add_quad(st,
				Vector3(center.x - hole_half, top_y, center.z + hole_half),
				Vector3(center.x - hole_half, top_y, center.z - hole_half),
				Vector3(center.x - bottom_half, bottom_y, center.z - bottom_half),
				Vector3(center.x - bottom_half, bottom_y, center.z + bottom_half),
				Vector3(0.99, 0.15, 0.0))
			_add_quad(st,
				Vector3(center.x + hole_half, top_y, center.z - hole_half),
				Vector3(center.x + hole_half, top_y, center.z + hole_half),
				Vector3(center.x + bottom_half, bottom_y, center.z + bottom_half),
				Vector3(center.x + bottom_half, bottom_y, center.z - bottom_half),
				Vector3(-0.99, 0.15, 0.0))

			# Dark bottom, slightly recessed, so the hole reads as real depth.
			_add_horizontal_quad(st,
				Vector3(center.x - bottom_half, bottom_y, center.z - bottom_half),
				Vector3(center.x + bottom_half, bottom_y, center.z - bottom_half),
				Vector3(center.x + bottom_half, bottom_y, center.z + bottom_half),
				Vector3(center.x - bottom_half, bottom_y, center.z + bottom_half))


func _build_underfill_columns(st: SurfaceTool) -> void:
	var half: float = cell_size * 0.5
	var gap: float = cell_size * tile_gap_ratio
	var outer_half: float = half - gap * 0.5
	var fill_half: float = maxf(outer_half - 0.040, cell_size * 0.30)
	for r: int in range(_rows):
		for c: int in range(_cols):
			var center: Vector3 = _cell_center(r, c)
			var top_y: float = _cell_top_y(r, c) - rim_drop - 0.010
			if top_y <= 0.0:
				continue
			var x0: float = center.x - fill_half
			var x1: float = center.x + fill_half
			var z0: float = center.z - fill_half
			var z1: float = center.z + fill_half
			var y0: float = 0.0
			var y1: float = top_y
			_add_quad(st, Vector3(x0,y1,z0), Vector3(x1,y1,z0), Vector3(x1,y0,z0), Vector3(x0,y0,z0), Vector3(0,0,-1))
			_add_quad(st, Vector3(x1,y1,z1), Vector3(x0,y1,z1), Vector3(x0,y0,z1), Vector3(x1,y0,z1), Vector3(0,0,1))
			_add_quad(st, Vector3(x0,y1,z1), Vector3(x0,y1,z0), Vector3(x0,y0,z0), Vector3(x0,y0,z1), Vector3(-1,0,0))
			_add_quad(st, Vector3(x1,y1,z0), Vector3(x1,y1,z1), Vector3(x1,y0,z1), Vector3(x1,y0,z0), Vector3(1,0,0))


func _make_fill_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = slope_tint.darkened(0.08)
	material.roughness = 1.0
	material.metallic = 0.0
	material.cull_mode = BaseMaterial3D.CULL_BACK
	return material


func update_dynamic_state(state: GameState, animation_duration: float = 0.12) -> void:
	if props != null:
		props.update_dynamic_state(state, self, animation_duration)


func get_cell_top_position(r: int, c: int) -> Vector3:
	var center: Vector3 = _cell_center(r, c)
	center.y = _cell_top_y(r, c) + 0.001
	return center


func get_cell_level(r: int, c: int) -> int:
	if r < 0 or r >= _rows or c < 0 or c >= _cols:
		return 1
	return _level_at(r, c)


# -----------------------------------------------------------------------------
# BOARD COORDINATES / ELEVATION
# -----------------------------------------------------------------------------

func _cell_center(r: int, c: int) -> Vector3:
	var x: float = (float(c) - float(_cols - 1) * 0.5) * cell_size
	var z: float = (float(r) - float(_rows - 1) * 0.5) * cell_size
	return Vector3(x, 0.0, z)


func _cell_top_y(r: int, c: int) -> float:
	return float(_level_at(r, c)) * level_height


func _level_at(r: int, c: int) -> int:
	var row: Array = _height_map[r] as Array
	return clampi(int(row[c]), 1, 9)


func _level_at_or_zero(r: int, c: int) -> int:
	if r < 0 or r >= _rows or c < 0 or c >= _cols:
		return 0
	return _level_at(r, c)


func _resolve_rock_heights(source: Array) -> Array:
	var result: Array = []
	for source_row: Variant in source:
		var src: Array = source_row as Array
		var copy_row: Array[int] = []
		for value: Variant in src:
			copy_row.append(int(value))
		result.append(copy_row)

	# 0 is only the elevation.txt placeholder for a rock cell. For the plan-only
	# preview, infer the hidden ground height from reachable neighbours.
	for _pass: int in range(6):
		var changed: bool = false
		for r: int in range(result.size()):
			var row: Array = result[r] as Array
			for c: int in range(row.size()):
				if int(row[c]) != 0:
					continue
				var sum: int = 0
				var count: int = 0
				var directions: Array[Vector2i] = [
					Vector2i(-1, 0),
					Vector2i(1, 0),
					Vector2i(0, -1),
					Vector2i(0, 1),
				]
				for direction: Vector2i in directions:
					var nr: int = r + direction.y
					var nc: int = c + direction.x
					if nr >= 0 and nr < result.size():
						var neighbor_row: Array = result[nr] as Array
						if nc >= 0 and nc < neighbor_row.size():
							var neighbor: int = int(neighbor_row[nc])
							if neighbor > 0:
								sum += neighbor
								count += 1
				if count > 0:
					row[c] = clampi(int(round(float(sum) / float(count))), 1, 9)
					changed = true
		if not changed:
			break

	for row_value: Variant in result:
		var row: Array = row_value as Array
		for c: int in range(row.size()):
			if int(row[c]) == 0:
				row[c] = 1
	return result


func _average_height() -> float:
	var total: float = 0.0
	var count: int = 0
	for row_value: Variant in _height_map:
		var row: Array = row_value as Array
		for value: Variant in row:
			total += float(value)
			count += 1
	if count == 0:
		return 1.0
	return total / float(count)


# -----------------------------------------------------------------------------
# MESH HELPERS
# -----------------------------------------------------------------------------

func _add_horizontal_quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	_add_vertex(st, a, Vector3.UP, Vector2(0.0, 0.0))
	_add_vertex(st, d, Vector3.UP, Vector2(0.0, 1.0))
	_add_vertex(st, c, Vector3.UP, Vector2(1.0, 1.0))
	_add_vertex(st, a, Vector3.UP, Vector2(0.0, 0.0))
	_add_vertex(st, c, Vector3.UP, Vector2(1.0, 1.0))
	_add_vertex(st, b, Vector3.UP, Vector2(1.0, 0.0))


func _add_quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, normal: Vector3) -> void:
	var n: Vector3 = normal.normalized()
	_add_vertex(st, a, n, Vector2(0.0, 0.0))
	_add_vertex(st, d, n, Vector2(0.0, 1.0))
	_add_vertex(st, c, n, Vector2(1.0, 1.0))
	_add_vertex(st, a, n, Vector2(0.0, 0.0))
	_add_vertex(st, c, n, Vector2(1.0, 1.0))
	_add_vertex(st, b, n, Vector2(1.0, 0.0))


func _add_vertex(st: SurfaceTool, position: Vector3, normal: Vector3, uv: Vector2) -> void:
	st.set_normal(normal)
	st.set_uv(uv)
	st.add_vertex(position)


func _add_triangle(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, normal: Vector3) -> void:
	var n: Vector3 = normal.normalized()
	_add_vertex(st, a, n, Vector2(0.5, 0.0))
	_add_vertex(st, b, n, Vector2(0.0, 1.0))
	_add_vertex(st, c, n, Vector2(1.0, 1.0))


# -----------------------------------------------------------------------------
# MATERIALS
# Intentionally procedural for this validation step. This avoids the black-top
# import problem seen in the previous screenshot and guarantees a visible plan.
# -----------------------------------------------------------------------------

func _make_top_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = top_tint
	material.roughness = 0.88
	material.metallic = 0.0
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.emission_enabled = true
	material.emission = top_tint.darkened(0.18)
	material.emission_energy_multiplier = top_emission_strength
	return material


func _make_rim_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = rim_tint
	material.roughness = 0.94
	material.metallic = 0.0
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material


func _make_slope_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = slope_tint
	material.roughness = 1.0
	material.metallic = 0.0
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material
