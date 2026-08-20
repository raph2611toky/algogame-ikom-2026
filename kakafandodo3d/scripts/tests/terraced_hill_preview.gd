extends Node3D

const TERRAIN_FACTORY = preload("res://scripts/game/terrain/terraced_tile_mesh_factory.gd")
const FLOOR_TEXTURE: Texture2D = preload("res://assets/game/terrain/floor.svg")

# ÉTAPE 1 corrigée : on valide le PROFIL du terrain, pas une tuile isolée.
# Cette matrice forme une petite colline en terrasses :
# 1 1 1 1 1 1 1
# 1 2 2 2 2 2 1
# 1 2 3 3 3 2 1
# 1 2 3 4 3 2 1
# ... symétrique ...
const HEIGHTS := [
	[1, 1, 1, 1, 1, 1, 1],
	[1, 2, 2, 2, 2, 2, 1],
	[1, 2, 3, 3, 3, 2, 1],
	[1, 2, 3, 4, 3, 2, 1],
	[1, 2, 3, 3, 3, 2, 1],
	[1, 2, 2, 2, 2, 2, 1],
	[1, 1, 1, 1, 1, 1, 1],
]

const CELL_SIZE := 2.25
const LEVEL_HEIGHT := 0.72
const SLOPE_BAND_RATIO := 0.30

@onready var terrain_root: Node3D = $Terrain
@onready var collision_root: StaticBody3D = $TerrainCollision
@onready var camera: Camera3D = $Camera3D
@onready var title_label: Label = $UI/Title
@onready var info_label: Label = $UI/Info

func _ready() -> void:
	_build_terrain()
	camera.look_at(Vector3(0.0, LEVEL_HEIGHT * 1.7, 0.0), Vector3.UP)
	title_label.text = "ÉTAPE 1 — TERRAIN EN TERRASSES"
	info_label.text = "Plateaux plats • bordures inclinées • transitions 1 → 2 → 3 → 4 • aucune rampe ajoutée"

func _build_terrain() -> void:
	var flat_material := StandardMaterial3D.new()
	flat_material.albedo_color = Color("#d0a067")
	flat_material.albedo_texture = FLOOR_TEXTURE
	flat_material.roughness = 0.88
	flat_material.metallic = 0.0
	flat_material.cull_mode = BaseMaterial3D.CULL_DISABLED

	var slope_material := StandardMaterial3D.new()
	slope_material.albedo_color = Color("#8a5734")
	slope_material.roughness = 0.96
	slope_material.metallic = 0.0
	slope_material.cull_mode = BaseMaterial3D.CULL_DISABLED

	var rows := HEIGHTS.size()
	var cols := HEIGHTS[0].size()
	var origin_x := -float(cols - 1) * CELL_SIZE * 0.5
	var origin_z := -float(rows - 1) * CELL_SIZE * 0.5

	for row in range(rows):
		for col in range(cols):
			var elevation: int = HEIGHTS[row][col]
			var north := _height_or_missing(row - 1, col)
			var east := _height_or_missing(row, col + 1)
			var south := _height_or_missing(row + 1, col)
			var west := _height_or_missing(row, col - 1)

			var mesh: ArrayMesh = TERRAIN_FACTORY.create_cell_mesh(
				CELL_SIZE,
				elevation,
				north,
				east,
				south,
				west,
				LEVEL_HEIGHT,
				SLOPE_BAND_RATIO,
				flat_material,
				slope_material
			)

			var tile := MeshInstance3D.new()
			tile.name = "Cell_%d_%d_Z%d" % [row, col, elevation]
			tile.mesh = mesh
			tile.position = Vector3(origin_x + col * CELL_SIZE, 0.0, origin_z + row * CELL_SIZE)
			tile.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
			terrain_root.add_child(tile)

			# La collision est exactement la surface visible : la future machine ou
			# le futur personnage pourra donc suivre la montée sans collision cube.
			var collision := CollisionShape3D.new()
			collision.name = "Collision_%d_%d" % [row, col]
			collision.shape = mesh.create_trimesh_shape()
			collision.position = tile.position
			collision_root.add_child(collision)

func _height_or_missing(row: int, col: int) -> int:
	if row < 0 or row >= HEIGHTS.size():
		return TERRAIN_FACTORY.MISSING_NEIGHBOR
	if col < 0 or col >= HEIGHTS[row].size():
		return TERRAIN_FACTORY.MISSING_NEIGHBOR
	return HEIGHTS[row][col]
