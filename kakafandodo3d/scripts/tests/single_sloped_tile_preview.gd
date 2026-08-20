extends Node3D

const TILE_MESH_FACTORY = preload("res://scripts/game/terrain/sloped_tile_mesh_factory.gd")
const FLOOR_TEXTURE: Texture2D = preload("res://assets/game/terrain/floor.svg")

# ÉTAPE 1 : UNE SEULE CASE.
# On ne touche pas encore aux hauteurs 1..9, à la caméra dynamique, aux objets
# ou à la simulation. On valide d'abord la silhouette de la tuile.
const TOP_SIZE := 3.20
const BOTTOM_SIZE := 4.05
const TILE_HEIGHT := 1.15

@onready var camera: Camera3D = $Camera3D
@onready var tile_anchor: Node3D = $TileAnchor
@onready var title_label: Label = $UI/Title
@onready var shape_label: Label = $UI/Shape

func _ready() -> void:
	_build_single_tile()
	camera.look_at(Vector3(0.0, TILE_HEIGHT * 0.44, 0.0), Vector3.UP)
	title_label.text = "ÉTAPE 1 — UNE SEULE CASE"
	shape_label.text = "Dessus plat • 4 côtés inclinés • aucune rampe ajoutée"

func _build_single_tile() -> void:
	var side_material := StandardMaterial3D.new()
	side_material.albedo_color = Color("#6b4429")
	side_material.roughness = 0.92
	side_material.metallic = 0.0

	var top_material := StandardMaterial3D.new()
	top_material.albedo_color = Color("#e1c28d")
	top_material.albedo_texture = FLOOR_TEXTURE
	top_material.roughness = 0.76
	top_material.metallic = 0.0

	var tile_mesh: ArrayMesh = TILE_MESH_FACTORY.create_tile_mesh(
		TOP_SIZE,
		BOTTOM_SIZE,
		TILE_HEIGHT,
		top_material,
		side_material
	)

	var tile := MeshInstance3D.new()
	tile.name = "SingleSlopedTile"
	tile.mesh = tile_mesh
	tile.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	tile_anchor.add_child(tile)

	# Une collision trimesh est déjà prête sur la bonne pente. Elle n'est pas
	# encore utilisée par le gameplay, mais garantit que la forme visuelle pourra
	# devenir la forme physique sans ajouter de faux cube vertical.
	var static_body := StaticBody3D.new()
	static_body.name = "TileCollision"
	var collision := CollisionShape3D.new()
	collision.shape = tile_mesh.create_trimesh_shape()
	static_body.add_child(collision)
	tile_anchor.add_child(static_body)
