class_name TerracedTileMeshFactory
extends RefCounted

# Terrain en terrasse, conscient des voisins.
#
# Une case n'est PAS un tronc de pyramide indépendant.
# Le centre de la case reste un plateau horizontal. Seule la bande proche
# d'un bord devient inclinée lorsque le voisin est à une hauteur différente.
#
# Conséquence :
#   - même hauteur de part et d'autre -> surface continue et plate ;
#   - différence de 1 niveau -> pente continue entre les deux plateaux ;
#   - bord extérieur -> pente vers le sol ;
#
# Cette géométrie est la bonne base pour faire marcher ensuite les personnages
# et machines directement sur la pente avec une collision trimesh identique.

const MISSING_NEIGHBOR := -999

static func create_cell_mesh(
		cell_size: float,
		elevation: int,
		north_elevation: int,
		east_elevation: int,
		south_elevation: int,
		west_elevation: int,
		level_height: float,
		slope_band_ratio: float,
		flat_material: Material = null,
		slope_material: Material = null
	) -> ArrayMesh:
	var size := maxf(0.5, cell_size)
	var h := maxf(0.05, level_height) * max(0, elevation)
	var band := clampf(size * slope_band_ratio, size * 0.08, size * 0.40)
	var half := size * 0.5
	var core := half - band

	# 4 x 4 points : les quatre points du centre donnent un grand plateau plat,
	# les couronnes extérieures servent uniquement à créer les pentes.
	var xs := PackedFloat32Array([-half, -core, core, half])
	var zs := PackedFloat32Array([-half, -core, core, half])

	var edge_n := _edge_height(h, elevation, north_elevation, level_height)
	var edge_e := _edge_height(h, elevation, east_elevation, level_height)
	var edge_s := _edge_height(h, elevation, south_elevation, level_height)
	var edge_w := _edge_height(h, elevation, west_elevation, level_height)

	var heights: Array = []
	for z_i in range(4):
		var row: Array[float] = []
		for x_i in range(4):
			var point_h := h
			var on_n := z_i == 0
			var on_s := z_i == 3
			var on_w := x_i == 0
			var on_e := x_i == 3

			if on_n and on_w:
				point_h = (edge_n + edge_w) * 0.5
			elif on_n and on_e:
				point_h = (edge_n + edge_e) * 0.5
			elif on_s and on_w:
				point_h = (edge_s + edge_w) * 0.5
			elif on_s and on_e:
				point_h = (edge_s + edge_e) * 0.5
			elif on_n:
				point_h = edge_n
			elif on_s:
				point_h = edge_s
			elif on_w:
				point_h = edge_w
			elif on_e:
				point_h = edge_e

			row.append(point_h)
		heights.append(row)

	var mesh := ArrayMesh.new()
	var flat := SurfaceTool.new()
	var slopes := SurfaceTool.new()
	flat.begin(Mesh.PRIMITIVE_TRIANGLES)
	slopes.begin(Mesh.PRIMITIVE_TRIANGLES)
	var flat_count := 0
	var slope_count := 0

	for z_i in range(3):
		for x_i in range(3):
			var p00 := Vector3(xs[x_i], heights[z_i][x_i], zs[z_i])
			var p01 := Vector3(xs[x_i], heights[z_i + 1][x_i], zs[z_i + 1])
			var p11 := Vector3(xs[x_i + 1], heights[z_i + 1][x_i + 1], zs[z_i + 1])
			var p10 := Vector3(xs[x_i + 1], heights[z_i][x_i + 1], zs[z_i])

			var min_h: float = minf(minf(p00.y, p01.y), minf(p11.y, p10.y))
			var max_h: float = maxf(maxf(p00.y, p01.y), maxf(p11.y, p10.y))
			var is_flat := absf(max_h - min_h) < 0.001

			var u0 := float(x_i) / 3.0
			var u1 := float(x_i + 1) / 3.0
			var v0 := float(z_i) / 3.0
			var v1 := float(z_i + 1) / 3.0
			var target: SurfaceTool = flat if is_flat else slopes
			_add_quad(target, p00, p01, p11, p10, Vector2(u0, v0), Vector2(u0, v1), Vector2(u1, v1), Vector2(u1, v0))
			if is_flat:
				flat_count += 1
			else:
				slope_count += 1

	if flat_count > 0:
		flat.generate_normals()
		if flat_material != null:
			flat.set_material(flat_material)
		flat.commit(mesh)

	if slope_count > 0:
		slopes.generate_normals()
		if slope_material != null:
			slopes.set_material(slope_material)
		slopes.commit(mesh)

	return mesh

static func _edge_height(current_height: float, current_elevation: int, neighbor_elevation: int, level_height: float) -> float:
	if neighbor_elevation == MISSING_NEIGHBOR:
		# L'extérieur de la carte descend au sol. Dans la carte test, le pourtour
		# est Z1 : on obtient donc une pente douce, pas une falaise verticale.
		return 0.0

	var neighbor_height := max(0, neighbor_elevation) * maxf(0.05, level_height)
	if neighbor_elevation == current_elevation:
		return current_height

	# Les deux cellules partagent exactement la même hauteur à leur frontière.
	# Chacune fournit la moitié de la pente : aucune fissure et aucune rampe
	# indépendante n'est ajoutée entre les cases.
	return (current_height + neighbor_height) * 0.5

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
	st.set_uv(uv_a)
	st.add_vertex(a)
	st.set_uv(uv_b)
	st.add_vertex(b)
	st.set_uv(uv_c)
	st.add_vertex(c)

	st.set_uv(uv_a)
	st.add_vertex(a)
	st.set_uv(uv_c)
	st.add_vertex(c)
	st.set_uv(uv_d)
	st.add_vertex(d)
