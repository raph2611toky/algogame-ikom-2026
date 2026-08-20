class_name Plan3DPropSpawner
extends Node3D

const IKOTOFOSA_TEXTURE: Texture2D = preload("res://assets/game/characters/ikotofosa_clean.png")
const IMAHAKI_TEXTURE: Texture2D = preload("res://assets/game/characters/imahaki_clean.png")
const ROCK_TEXTURE: Texture2D = preload("res://assets/game/terrain/rock_clean.png")
const TREE_TEXTURE: Texture2D = preload("res://assets/game/terrain/tree_clean.png")
const HOLE_OVERLAY_TEXTURE: Texture2D = preload("res://assets/game/terrain/hole_leafy_overlay.png")
const BUSH_TEXTURE: Texture2D = preload("res://assets/game/terrain/bush_clean.png")
const CHEST_TEXTURE: Texture2D = preload("res://assets/game/props/chest_closed.png")
const GEM_TEXTURE: Texture2D = preload("res://assets/game/props/gem_clean.png")
const EXCAVATOR_TEXTURE: Texture2D = preload("res://assets/game/machines/excavator_clean.png")
const GRAPPLER_TEXTURE: Texture2D = preload("res://assets/game/machines/grappler_clean.png")

@export_group("Scale")
@export_range(0.35, 1.40, 0.01) var rock_height_ratio: float = 0.68
@export_range(0.50, 1.80, 0.01) var tree_height_ratio: float = 1.10
@export_range(0.25, 1.00, 0.01) var chest_height_ratio: float = 0.56
@export_range(0.20, 0.90, 0.01) var gem_height_ratio: float = 0.52
@export_range(0.20, 1.00, 0.01) var bush_height_ratio: float = 0.40
@export_range(0.45, 1.50, 0.01) var machine_height_ratio: float = 0.74
@export_range(0.45, 1.50, 0.01) var character_height_ratio: float = 0.92

@export_group("Maximum width in cell")
@export_range(0.40, 1.20, 0.01) var rock_width_ratio: float = 0.82
@export_range(0.40, 1.20, 0.01) var tree_width_ratio: float = 0.82
@export_range(0.30, 1.20, 0.01) var chest_width_ratio: float = 0.70
@export_range(0.20, 1.00, 0.01) var gem_width_ratio: float = 0.40
@export_range(0.30, 1.20, 0.01) var bush_width_ratio: float = 0.62
@export_range(0.50, 1.35, 0.01) var machine_width_ratio: float = 0.84
@export_range(0.30, 1.00, 0.01) var character_width_ratio: float = 0.64
@export_range(0.40, 1.20, 0.01) var hole_width_ratio: float = 1.10

var _static_root: Node3D
var _dynamic_root: Node3D
var _dynamic_nodes: Dictionary = {}
var _dynamic_tweens: Dictionary = {}
var _used_rect_cache: Dictionary = {}

func _ready() -> void:
	_ensure_roots()

func _ensure_roots() -> void:
	if _static_root == null or not is_instance_valid(_static_root):
		_static_root = Node3D.new()
		_static_root.name = "StaticProps"
		add_child(_static_root)
	if _dynamic_root == null or not is_instance_valid(_dynamic_root):
		_dynamic_root = Node3D.new()
		_dynamic_root.name = "DynamicEntities"
		add_child(_dynamic_root)

# Compatibility alias used by old previews.
func populate(map_grid: Array[String], board: Plan3DGenerator) -> void:
	populate_static(map_grid, board)

func populate_static(map_grid: Array[String], board: Plan3DGenerator) -> void:
	_ensure_roots()
	for child: Node in _static_root.get_children():
		child.queue_free()
	if map_grid.is_empty():
		return
	for row: int in range(map_grid.size()):
		var line: String = map_grid[row]
		for col: int in range(line.length()):
			var symbol: String = line.substr(col, 1)
			match symbol:
				"#": _spawn_static_visual("Rock", ROCK_TEXTURE, row, col, board, rock_height_ratio, rock_width_ratio, -0.045)
				"t": _spawn_static_visual("Tree", TREE_TEXTURE, row, col, board, tree_height_ratio, tree_width_ratio, -0.035)
				"o": _spawn_hole_overlay(row, col, board)
				"@": _spawn_static_visual("Bush", BUSH_TEXTURE, row, col, board, bush_height_ratio, bush_width_ratio, -0.028)
				_: pass

func update_dynamic_state(state: GameState, board: Plan3DGenerator, animation_duration: float = 0.12) -> void:
	_ensure_roots()
	if state == null:
		return
	var wanted: Dictionary = {}

	for hero_id in ["F", "M"]:
		if not state.heroes.has(hero_id):
			continue
		var hero: Dictionary = state.heroes[hero_id]
		var texture: Texture2D = IKOTOFOSA_TEXTURE if hero_id == "F" else IMAHAKI_TEXTURE
		wanted["hero:%s" % hero_id] = {
			"texture": texture,
			"pos": Vector2i(hero["pos"]),
			"height_ratio": character_height_ratio,
			"width_ratio": character_width_ratio,
			"base_offset": -0.050 if hero_id == "F" else -0.046,
			"kind": "hero",
		}

	for machine_id_value in state.machines.keys():
		var machine_id: String = str(machine_id_value)
		var machine: Dictionary = state.machines[machine_id]
		var kind: String = str(machine["kind"])
		wanted["machine:%s" % machine_id] = {
			"texture": EXCAVATOR_TEXTURE if kind == "X" else GRAPPLER_TEXTURE,
			"pos": Vector2i(machine["pos"]),
			"height_ratio": machine_height_ratio,
			"width_ratio": machine_width_ratio,
			"base_offset": -0.042,
			"kind": "machine",
		}

	for chest_id_value in state.chests.keys():
		var chest_id: String = str(chest_id_value)
		var chest: Dictionary = state.chests[chest_id]
		wanted["chest:%s" % chest_id] = {
			"texture": CHEST_TEXTURE,
			"pos": Vector2i(chest["pos"]),
			"height_ratio": chest_height_ratio,
			"width_ratio": chest_width_ratio,
			"base_offset": -0.040,
			"kind": "chest",
		}

	for stone_pos_value in state.stones.keys():
		var stone_pos: Vector2i = Vector2i(stone_pos_value)
		var count: int = int(state.stones.get(stone_pos, 0))
		for index: int in range(count):
			wanted["stone:%d:%d:%d" % [stone_pos.x, stone_pos.y, index]] = {
				"texture": GEM_TEXTURE,
				"pos": stone_pos,
				"height_ratio": gem_height_ratio,
				"width_ratio": gem_width_ratio,
				"base_offset": -0.034,
				"kind": "stone",
			}

	var to_remove: Array = []
	for key_value in _dynamic_nodes.keys():
		var key: String = str(key_value)
		if not wanted.has(key):
			to_remove.append(key)
	for key_value in to_remove:
		var key: String = str(key_value)
		if _dynamic_tweens.has(key):
			var old_tween: Tween = _dynamic_tweens[key] as Tween
			if old_tween != null and old_tween.is_valid():
				old_tween.kill()
			_dynamic_tweens.erase(key)
		var old_node: Node3D = _dynamic_nodes[key] as Node3D
		if is_instance_valid(old_node):
			old_node.queue_free()
		_dynamic_nodes.erase(key)

	for key_value in wanted.keys():
		var key: String = str(key_value)
		var data: Dictionary = wanted[key]
		var texture: Texture2D = data["texture"] as Texture2D
		var sprite: Sprite3D
		if not _dynamic_nodes.has(key) or not is_instance_valid(_dynamic_nodes[key]):
			sprite = _create_sprite(texture, float(data["height_ratio"]), float(data["width_ratio"]), board)
			sprite.name = key.replace(":", "_")
			_dynamic_root.add_child(sprite)
			_dynamic_nodes[key] = sprite
			sprite.position = _entity_world_position(sprite, data, board)
		else:
			sprite = _dynamic_nodes[key] as Sprite3D
			var target: Vector3 = _entity_world_position(sprite, data, board)
			if _dynamic_tweens.has(key):
				var old: Tween = _dynamic_tweens[key] as Tween
				if old != null and old.is_valid():
					old.kill()
			if animation_duration > 0.01 and sprite.position.distance_to(target) > 0.01:
				var tween: Tween = create_tween()
				tween.set_trans(Tween.TRANS_SINE)
				tween.set_ease(Tween.EASE_IN_OUT)
				tween.tween_property(sprite, "position", target, animation_duration)
				_dynamic_tweens[key] = tween
			else:
				sprite.position = target

func _entity_world_position(sprite: Sprite3D, data: Dictionary, board: Plan3DGenerator) -> Vector3:
	var pos: Vector2i = Vector2i(data["pos"])
	var top: Vector3 = board.get_cell_top_position(pos.y, pos.x)
	var rect: Rect2i = _get_used_rect(sprite.texture)
	var visible_height: float = float(rect.size.y) * sprite.pixel_size
	return Vector3(top.x, top.y + visible_height * 0.5 + float(data["base_offset"]), top.z)

func _spawn_static_visual(prefix: String, texture: Texture2D, row: int, col: int, board: Plan3DGenerator, height_ratio: float, width_ratio: float, base_offset: float) -> void:
	var sprite: Sprite3D = _create_sprite(texture, height_ratio, width_ratio, board)
	sprite.name = "%s_%d_%d" % [prefix, row, col]
	var rect: Rect2i = _get_used_rect(texture)
	var visible_height: float = float(rect.size.y) * sprite.pixel_size
	var top: Vector3 = board.get_cell_top_position(row, col)
	sprite.position = Vector3(top.x, top.y + visible_height * 0.5 + base_offset, top.z)
	_static_root.add_child(sprite)

func _create_sprite(texture: Texture2D, height_ratio: float, width_ratio: float, board: Plan3DGenerator) -> Sprite3D:
	var rect: Rect2i = _get_used_rect(texture)
	var bbox_w: float = maxf(1.0, float(rect.size.x))
	var bbox_h: float = maxf(1.0, float(rect.size.y))
	var pixel_size: float = minf((board.cell_size * height_ratio) / bbox_h, (board.cell_size * width_ratio) / bbox_w)
	var tex_w: float = maxf(1.0, float(texture.get_width()))
	var tex_h: float = maxf(1.0, float(texture.get_height()))
	var bbox_center_x: float = float(rect.position.x) + bbox_w * 0.5
	var bbox_center_y: float = float(rect.position.y) + bbox_h * 0.5

	var sprite := Sprite3D.new()
	sprite.texture = texture
	sprite.centered = true
	sprite.pixel_size = pixel_size
	sprite.offset = Vector2(tex_w * 0.5 - bbox_center_x, tex_h * 0.5 - bbox_center_y)
	sprite.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
	sprite.shaded = false
	sprite.double_sided = true
	sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
	sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return sprite

func _get_used_rect(texture: Texture2D) -> Rect2i:
	var key: String = texture.resource_path
	if _used_rect_cache.has(key):
		return _used_rect_cache[key]
	var image: Image = texture.get_image()
	var rect: Rect2i = image.get_used_rect()
	if rect.size.x <= 0 or rect.size.y <= 0:
		rect = Rect2i(0, 0, int(texture.get_width()), int(texture.get_height()))
	_used_rect_cache[key] = rect
	return rect

func _spawn_hole_overlay(row: int, col: int, board: Plan3DGenerator) -> void:
	var top: Vector3 = board.get_cell_top_position(row, col)
	var quad := MeshInstance3D.new()
	quad.name = "HoleOverlay_%d_%d" % [row, col]
	var mesh := QuadMesh.new()
	mesh.size = Vector2(board.cell_size * hole_width_ratio, board.cell_size * hole_width_ratio)
	quad.mesh = mesh
	quad.rotation_degrees.x = -90.0
	quad.position = Vector3(top.x, top.y + 0.004, top.z)
	var material := StandardMaterial3D.new()
	material.albedo_texture = HOLE_OVERLAY_TEXTURE
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	quad.material_override = material
	quad.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_static_root.add_child(quad)
