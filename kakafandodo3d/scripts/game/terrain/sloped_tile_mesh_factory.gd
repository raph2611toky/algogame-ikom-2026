class_name SlopedTileMeshFactory
extends RefCounted

# Fabrique la forme de base DEFINITIVE d'une case Kakafandodo :
# - dessus carré et plat ;
# - base carrée un peu plus large ;
# - les 4 faces latérales sont inclinées ;
# - aucune rampe extérieure, aucun BoxMesh vertical.
#
# Cette géométrie sera réutilisée ensuite pour Z1 ... Z9.

static func create_tile_mesh(
		top_size: float,
		bottom_size: float,
		height: float,
		top_material: Material = null,
		side_material: Material = null
	) -> ArrayMesh:
	var safe_top := maxf(0.05, top_size)
	var safe_bottom := maxf(safe_top + 0.02, bottom_size)
	var safe_height := maxf(0.05, height)

	var top_half := safe_top * 0.5
	var bottom_half := safe_bottom * 0.5

	# Sommets du bas.
	var b_nw := Vector3(-bottom_half, 0.0, -bottom_half)
	var b_ne := Vector3(bottom_half, 0.0, -bottom_half)
	var b_se := Vector3(bottom_half, 0.0, bottom_half)
	var b_sw := Vector3(-bottom_half, 0.0, bottom_half)

	# Sommets du dessus : plus rentrés => quatre flancs naturellement inclinés.
	var t_nw := Vector3(-top_half, safe_height, -top_half)
	var t_ne := Vector3(top_half, safe_height, -top_half)
	var t_se := Vector3(top_half, safe_height, top_half)
	var t_sw := Vector3(-top_half, safe_height, top_half)

	var mesh := ArrayMesh.new()

	# -------------------------------------------------------------------------
	# Surface 0 : les 4 côtés inclinés + dessous.
	# Chaque face a ses propres sommets pour obtenir des arêtes nettes.
	# -------------------------------------------------------------------------
	var sides := SurfaceTool.new()
	sides.begin(Mesh.PRIMITIVE_TRIANGLES)

	# Nord (-Z) — winding vers l'extérieur.
	_add_quad(sides, b_ne, b_nw, t_nw, t_ne, Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0))
	# Est (+X)
	_add_quad(sides, b_se, b_ne, t_ne, t_se, Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0))
	# Sud (+Z)
	_add_quad(sides, b_sw, b_se, t_se, t_sw, Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0))
	# Ouest (-X)
	_add_quad(sides, b_nw, b_sw, t_sw, t_nw, Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0))

	# Dessous fermé, normale vers -Y.
	_add_quad(sides, b_nw, b_ne, b_se, b_sw, Vector2.ZERO, Vector2.RIGHT, Vector2.ONE, Vector2.DOWN)

	sides.generate_normals()
	if side_material != null:
		sides.set_material(side_material)
	sides.commit(mesh)

	# -------------------------------------------------------------------------
	# Surface 1 : dessus carré parfaitement horizontal.
	# -------------------------------------------------------------------------
	var top := SurfaceTool.new()
	top.begin(Mesh.PRIMITIVE_TRIANGLES)
	_add_quad(
		top,
		t_nw, t_sw, t_se, t_ne,
		Vector2(0, 0), Vector2(0, 1), Vector2(1, 1), Vector2(1, 0)
	)
	top.generate_normals()
	if top_material != null:
		top.set_material(top_material)
	top.commit(mesh)

	return mesh

static func _add_quad(
		st: SurfaceTool,
		a: Vector3,
		b: Vector3,
		c: Vector3,
		d: Vector3,
		uv_a: Vector2,
		uv_b: Vector2,
		uv_c: Vector2,
		uv_d: Vector2
	) -> void:
	# Triangle 1
	st.set_uv(uv_a)
	st.add_vertex(a)
	st.set_uv(uv_b)
	st.add_vertex(b)
	st.set_uv(uv_c)
	st.add_vertex(c)

	# Triangle 2
	st.set_uv(uv_a)
	st.add_vertex(a)
	st.set_uv(uv_c)
	st.add_vertex(c)
	st.set_uv(uv_d)
	st.add_vertex(d)
