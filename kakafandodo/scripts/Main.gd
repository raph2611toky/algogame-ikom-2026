extends Node3D

const TEX_WALL := "res://assets/textures/stone_wall.png"
const TEX_ARCH := "res://assets/textures/stone_arch_inner.png"
const TEX_LIGHT := "res://assets/textures/stone_light.png"
const TEX_DARK := "res://assets/textures/stone_dark.png"
const TEX_BASE := "res://assets/textures/stone_base.png"

var MAT := {}

func _ready() -> void:
	name = "Main"
	_build_materials()
	_build_environment()
	_build_camera()
	_build_lights()
	_build_facade()


func _build_materials() -> void:
	MAT.wall = _make_material(TEX_WALL, Color(1.0, 1.0, 1.0), 1.0)
	MAT.arch = _make_material(TEX_ARCH, Color(1.0, 0.94, 0.84), 1.0)
	MAT.light = _make_material(TEX_LIGHT, Color(1.0, 0.98, 0.93), 1.0)
	MAT.dark = _make_material(TEX_DARK, Color(0.85, 0.85, 0.85), 1.0)
	MAT.base = _make_material(TEX_BASE, Color(1.0, 0.97, 0.92), 1.0)
	MAT.shadow = StandardMaterial3D.new()
	MAT.shadow.albedo_color = Color(0.30, 0.24, 0.16)
	MAT.shadow.roughness = 1.0
	MAT.shadow.metallic = 0.0
	MAT.shadow.cull_mode = BaseMaterial3D.CULL_DISABLED
	MAT.flag_red = StandardMaterial3D.new()
	MAT.flag_red.albedo_color = Color(0.8, 0.14, 0.12)
	MAT.flag_red.roughness = 0.85
	MAT.flag_white = StandardMaterial3D.new()
	MAT.flag_white.albedo_color = Color(0.95, 0.95, 0.95)
	MAT.flag_white.roughness = 0.85
	MAT.gold = StandardMaterial3D.new()
	MAT.gold.albedo_color = Color(0.67, 0.49, 0.22)
	MAT.gold.roughness = 0.95
	MAT.green = StandardMaterial3D.new()
	MAT.green.albedo_color = Color(0.27, 0.42, 0.18)
	MAT.green.roughness = 1.0


func _make_material(texture_path: String, tint: Color, roughness: float) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = tint
	mat.roughness = roughness
	mat.metallic = 0.0
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	mat.cull_mode = BaseMaterial3D.CULL_BACK
	mat.uv1_triplanar = true
	mat.uv1_scale = Vector3(1.4, 1.4, 1.4)
	if ResourceLoader.exists(texture_path):
		mat.albedo_texture = load(texture_path)
	return mat


func _build_environment() -> void:
	var env := WorldEnvironment.new()
	env.name = "WorldEnvironment"
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.47, 0.72, 0.98)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(1.0, 1.0, 1.0)
	e.ambient_light_energy = 1.1
	e.ssao_enabled = true
	e.ssil_enabled = true
	e.glow_enabled = false
	env.environment = e
	add_child(env)


func _build_camera() -> void:
	var pivot := Node3D.new()
	pivot.name = "CameraRig"
	add_child(pivot)

	var cam := Camera3D.new()
	cam.name = "Camera3D"
	cam.position = Vector3(0.0, 4.55, 17.0)
	cam.rotation_degrees = Vector3(-1.5, 0.0, 0.0)
	cam.fov = 31.0
	cam.near = 0.05
	cam.far = 100.0
	pivot.add_child(cam)
	cam.look_at(Vector3(0.0, 4.0, 0.0), Vector3.UP)


func _build_lights() -> void:
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_energy = 2.6
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.rotation_degrees = Vector3(-48.0, -20.0, 0.0)
	sun.shadow_enabled = true
	add_child(sun)

	var fill := DirectionalLight3D.new()
	fill.name = "Fill"
	fill.light_energy = 0.55
	fill.light_color = Color(0.78, 0.86, 1.0)
	fill.rotation_degrees = Vector3(-15.0, 165.0, 0.0)
	fill.shadow_enabled = false
	add_child(fill)


func _build_facade() -> void:
	var facade := Node3D.new()
	facade.name = "Facade"
	add_child(facade)

	_build_lower_platform(facade)
	_build_main_mass(facade)
	_build_arch_opening(facade)
	_build_columns(facade)
	_build_pediment(facade)
	_build_side_attachments(facade)
	_build_roof_details(facade)
	_build_eagle(facade)
	_build_optional_side_foliage(facade)


func _build_lower_platform(root: Node3D) -> void:
	# base stairs / podium seen at the bottom of the facade crop
	_box(root, "Step01", Vector3(0.0, -0.15, 0.0), Vector3(9.8, 0.35, 2.2), MAT.base)
	_box(root, "Step02", Vector3(0.0, 0.18, -0.25), Vector3(8.4, 0.28, 1.8), MAT.base)
	_box(root, "Step03", Vector3(0.0, 0.44, -0.42), Vector3(7.0, 0.24, 1.2), MAT.base)
	_box(root, "TopWalk", Vector3(0.0, 0.62, -0.62), Vector3(5.4, 0.18, 0.95), MAT.base)


func _build_main_mass(root: Node3D) -> void:
	# rear frontal wall mass (shallow because user wants only the front part)
	_box(root, "CenterBody", Vector3(0.0, 3.75, -0.75), Vector3(9.6, 6.7, 0.85), MAT.wall)
	# lower side plinths
	_box(root, "LeftBaseBlock", Vector3(-4.25, 0.95, -0.35), Vector3(1.4, 1.1, 0.78), MAT.base)
	_box(root, "RightBaseBlock", Vector3(4.25, 0.95, -0.35), Vector3(1.4, 1.1, 0.78), MAT.base)
	# recessed side niches (shadows)
	_box(root, "LeftNicheBack", Vector3(-4.35, 2.15, -1.10), Vector3(0.95, 2.55, 0.12), MAT.shadow)
	_box(root, "RightNicheBack", Vector3(4.35, 2.15, -1.10), Vector3(0.95, 2.55, 0.12), MAT.shadow)
	# niche frames
	_box(root, "LeftNicheFrameTop", Vector3(-4.35, 3.50, -0.58), Vector3(1.15, 0.22, 0.35), MAT.base)
	_box(root, "RightNicheFrameTop", Vector3(4.35, 3.50, -0.58), Vector3(1.15, 0.22, 0.35), MAT.base)
	# long cornice above the arch
	_box(root, "MainCornice", Vector3(0.0, 5.78, -0.45), Vector3(10.0, 0.32, 1.15), MAT.dark)
	_box(root, "MainCorniceLower", Vector3(0.0, 5.54, -0.35), Vector3(9.8, 0.16, 1.0), MAT.base)
	# upper left / right wall blocks
	_box(root, "LeftUpperBlock", Vector3(-2.85, 6.55, -0.88), Vector3(3.45, 1.62, 1.25), MAT.dark)
	_box(root, "RightUpperBlock", Vector3(2.85, 6.55, -0.88), Vector3(3.45, 1.62, 1.25), MAT.dark)
	# slightly inset light caps below them
	_box(root, "LeftUpperCap", Vector3(-2.85, 5.96, -0.45), Vector3(3.3, 0.20, 0.95), MAT.base)
	_box(root, "RightUpperCap", Vector3(2.85, 5.96, -0.45), Vector3(3.3, 0.20, 0.95), MAT.base)


func _build_arch_opening(root: Node3D) -> void:
	# the opening itself is made by not placing a center wall mesh.
	# side jamb masses
	_box(root, "LeftJamb", Vector3(-2.35, 2.95, -0.10), Vector3(1.00, 4.55, 0.85), MAT.wall)
	_box(root, "RightJamb", Vector3(2.35, 2.95, -0.10), Vector3(1.00, 4.55, 0.85), MAT.wall)
	# spandrels around the arch
	_box(root, "LeftSpandrel", Vector3(-1.30, 5.15, -0.12), Vector3(1.28, 1.15, 0.85), MAT.wall)
	_box(root, "RightSpandrel", Vector3(1.30, 5.15, -0.12), Vector3(1.28, 1.15, 0.85), MAT.wall)
	# inner vault depth (front only, but enough to feel 3D)
	for d in range(6):
		var z := -0.30 - float(d) * 0.20
		_build_arch_ring(root, 0.0, 3.05, 2.18 - float(d) * 0.04, 1.82 - float(d) * 0.03, z, MAT.arch, "VaultRing_%d" % d)
	# front facing stones around arch
	_build_arch_ring(root, 0.0, 3.02, 2.45, 2.05, 0.05, MAT.base, "FrontArchRing")
	# interior side returns of the tunnel
	_box(root, "InnerLeftReturn", Vector3(-1.76, 2.15, -0.78), Vector3(0.18, 2.25, 1.55), MAT.arch)
	_box(root, "InnerRightReturn", Vector3(1.76, 2.15, -0.78), Vector3(0.18, 2.25, 1.55), MAT.arch)
	# low arch sill
	_box(root, "ArchSill", Vector3(0.0, 0.87, -0.56), Vector3(3.82, 0.18, 0.9), MAT.base)


func _build_arch_ring(root: Node3D, cx: float, cy: float, outer_r: float, inner_r: float, z: float, mat: Material, prefix: String) -> void:
	var steps := 15
	for i in range(steps):
		var t := float(i) / float(steps - 1)
		var a := lerp(PI, 0.0, t)
		var r := (outer_r + inner_r) * 0.5
		var p := Vector3(cx + cos(a) * r, cy + sin(a) * r, z)
		var block := _box(root, "%s_%d" % [prefix, i], p, Vector3(0.44, 0.44, 0.46), mat)
		block.rotation.z = -a + PI * 0.5


func _build_columns(root: Node3D) -> void:
	var xs := [-4.75, -3.05, 3.05, 4.75]
	for i in range(xs.size()):
		_build_column(root, xs[i], 2.90)
	# little ornamental blocks behind upper columns
	_box(root, "LeftSmallPier", Vector3(-4.05, 5.32, -0.18), Vector3(0.42, 0.55, 0.55), MAT.base)
	_box(root, "RightSmallPier", Vector3(4.05, 5.32, -0.18), Vector3(0.42, 0.55, 0.55), MAT.base)


func _build_column(root: Node3D, x: float, h_center: float) -> void:
	var col := Node3D.new()
	col.name = "Column_%s" % str(x)
	col.position = Vector3(x, 0.0, 0.0)
	root.add_child(col)
	_box(col, "Base", Vector3(0.0, 0.50, 0.0), Vector3(0.92, 0.34, 0.78), MAT.base)
	_box(col, "BaseTop", Vector3(0.0, 0.77, 0.0), Vector3(0.76, 0.14, 0.62), MAT.base)
	_cylinder(col, "ShaftLower", Vector3(0.0, 1.40, 0.0), 0.20, 1.04, MAT.wall)
	_cylinder(col, "RingMid", Vector3(0.0, 1.96, 0.0), 0.28, 0.10, MAT.base)
	_cylinder(col, "ShaftUpper", Vector3(0.0, 2.62, 0.0), 0.18, 1.14, MAT.wall)
	_cylinder(col, "CapitalRing", Vector3(0.0, 3.28, 0.0), 0.30, 0.12, MAT.base)
	_box(col, "CapitalBlock", Vector3(0.0, 3.53, 0.0), Vector3(0.74, 0.28, 0.58), MAT.base)


func _build_pediment(root: Node3D) -> void:
	# central triangle / gable
	var ped := MeshInstance3D.new()
	ped.name = "Pediment"
	var prism := PrismMesh.new()
	prism.size = Vector3(3.15, 1.55, 0.82)
	ped.mesh = prism
	ped.material_override = MAT.light
	ped.position = Vector3(0.0, 6.38, -0.44)
	ped.rotation_degrees = Vector3(0.0, 180.0, 180.0)
	root.add_child(ped)
	# pediment base band
	_box(root, "PedimentBase", Vector3(0.0, 5.98, -0.40), Vector3(3.75, 0.20, 0.78), MAT.base)
	# center support under eagle
	_box(root, "PedestalCore", Vector3(0.0, 7.42, -0.52), Vector3(0.46, 1.44, 0.50), MAT.wall)


func _build_side_attachments(root: Node3D) -> void:
	# left and right wing pilaster blocks near the top facade edges
	_box(root, "LeftOuterShoulder", Vector3(-5.35, 5.32, -0.30), Vector3(0.55, 0.60, 0.70), MAT.base)
	_box(root, "RightOuterShoulder", Vector3(5.35, 5.32, -0.30), Vector3(0.55, 0.60, 0.70), MAT.base)
	_box(root, "LeftOuterCap", Vector3(-5.35, 5.78, -0.24), Vector3(0.76, 0.18, 0.88), MAT.dark)
	_box(root, "RightOuterCap", Vector3(5.35, 5.78, -0.24), Vector3(0.76, 0.18, 0.88), MAT.dark)
	# tiny little decorative slits implied in the source image
	_box(root, "LeftSmallVoid", Vector3(-4.05, 4.57, -0.92), Vector3(0.24, 0.38, 0.06), MAT.shadow)
	_box(root, "RightSmallVoid", Vector3(4.05, 4.57, -0.92), Vector3(0.24, 0.38, 0.06), MAT.shadow)


func _build_roof_details(root: Node3D) -> void:
	# left chimney
	_cylinder(root, "Chimney", Vector3(-2.85, 7.82, -0.92), 0.18, 1.30, MAT.light)
	_cylinder(root, "ChimneyCap", Vector3(-2.85, 8.49, -0.92), 0.22, 0.10, MAT.base)
	# right tower / roof hint
	_box(root, "RightRearTower", Vector3(5.25, 7.25, -1.55), Vector3(1.25, 2.05, 1.20), MAT.light)
	_sphere(root, "RoofDome", Vector3(5.25, 8.25, -1.52), Vector3(0.82, 0.34, 0.82), MAT.light)
	# tiny Madagascar flag hint like the image
	_cylinder(root, "FlagPole", Vector3(2.25, 7.02, -0.75), 0.03, 0.85, MAT.dark)
	_box(root, "FlagWhite", Vector3(2.36, 7.18, -0.72), Vector3(0.18, 0.14, 0.02), MAT.flag_white)
	_box(root, "FlagRed", Vector3(2.50, 7.18, -0.72), Vector3(0.18, 0.14, 0.02), MAT.flag_red)


func _build_eagle(root: Node3D) -> void:
	var eagle := Node3D.new()
	eagle.name = "EagleStatue"
	eagle.position = Vector3(0.0, 8.38, -0.35)
	root.add_child(eagle)
	# body
	_box(eagle, "Body", Vector3(0.0, 0.10, 0.0), Vector3(0.30, 0.46, 0.24), MAT.gold)
	_box(eagle, "Head", Vector3(0.0, 0.42, 0.05), Vector3(0.16, 0.16, 0.16), MAT.gold)
	_box(eagle, "Beak", Vector3(0.0, 0.38, 0.18), Vector3(0.10, 0.05, 0.08), MAT.gold)
	# wings
	var left_wing := _box(eagle, "WingLeft", Vector3(-0.34, 0.22, 0.0), Vector3(0.56, 0.12, 0.26), MAT.gold)
	left_wing.rotation.z = deg_to_rad(28.0)
	var right_wing := _box(eagle, "WingRight", Vector3(0.34, 0.22, 0.0), Vector3(0.56, 0.12, 0.26), MAT.gold)
	right_wing.rotation.z = deg_to_rad(-28.0)
	_box(eagle, "Tail", Vector3(0.0, -0.12, -0.12), Vector3(0.18, 0.14, 0.24), MAT.gold)


func _build_optional_side_foliage(root: Node3D) -> void:
	# small leafy hints at the left / right edges just so the façade reads like the source image
	for i in range(5):
		var left_leaf := _box(root, "LeafL_%d" % i, Vector3(-6.1 - randf() * 0.5, 2.0 + float(i) * 1.0, -1.65), Vector3(0.50, 0.18, 0.05), MAT.green)
		left_leaf.rotation_degrees = Vector3(0.0, 0.0, -40.0 + i * 8.0)
		var right_leaf := _box(root, "LeafR_%d" % i, Vector3(6.1 + randf() * 0.5, 2.0 + float(i) * 1.0, -1.65), Vector3(0.50, 0.18, 0.05), MAT.green)
		right_leaf.rotation_degrees = Vector3(0.0, 0.0, 40.0 - i * 8.0)


func _box(parent: Node, node_name: String, pos: Vector3, size: Vector3, material: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = node_name
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = material
	mi.position = pos
	parent.add_child(mi)
	return mi


func _cylinder(parent: Node, node_name: String, pos: Vector3, radius: float, height: float, material: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = node_name
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 18
	mesh.rings = 3
	mi.mesh = mesh
	mi.material_override = material
	mi.position = pos
	parent.add_child(mi)
	return mi


func _sphere(parent: Node, node_name: String, pos: Vector3, scale_vec: Vector3, material: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = node_name
	var mesh := SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 20
	mesh.rings = 10
	mi.mesh = mesh
	mi.material_override = material
	mi.position = pos
	mi.scale = scale_vec
	parent.add_child(mi)
	return mi
