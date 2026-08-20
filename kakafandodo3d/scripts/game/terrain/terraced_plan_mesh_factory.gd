class_name TerracedPlanMeshFactory
extends RefCounted

# Relief continu en terrasses pour elevation.txt.
# Le centre des cellules reste plat. Les changements de niveau se font dans
# une bande de transition autour de la frontière entre deux cellules.
# Le mesh est construit avec des normales explicites orientées vers le haut,
# afin d'éviter les faces noires/invisibles suivant l'angle de caméra.

const MIN_LEVEL: int = 1
const MAX_LEVEL: int = 9

static func create_plan_mesh(
		height_map: Array,
		cell_size: float,
		base_height: float,
		level_height: float,
		transition_ratio: float,
		outer_slope_ratio: float,
		material: Material,
		subdivisions_per_cell: int = 6
	) -> ArrayMesh:
	var rows: int = height_map.size()
	if rows <= 0:
		return ArrayMesh.new()
	var cols: int = (height_map[0] as Array).size()
	if cols <= 0:
		return ArrayMesh.new()

	var resolved: Array = _resolve_non_significant_zeroes(height_map)
	var cell: float = maxf(0.25, cell_size)
	var subdivisions: int = maxi(1, subdivisions_per_cell)
	var transition_width: float = clampf(transition_ratio, 0.08, 0.48)
	var outer_margin_cells: float = clampf(outer_slope_ratio, 0.25, 1.35)

	var margin_steps: int = maxi(2, int(ceil(outer_margin_cells * float(subdivisions))))
	var x_segments: int = cols * subdivisions + margin_steps * 2
	var z_segments: int = rows * subdivisions + margin_steps * 2
	var vertex_cols: int = x_segments + 1
	var vertex_rows: int = z_segments + 1
	var vertex_count: int = vertex_cols * vertex_rows

	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	vertices.resize(vertex_count)
	normals.resize(vertex_count)
	uvs.resize(vertex_count)

	# 1) Positions + UV.
	for zi in range(vertex_rows):
		for xi in range(vertex_cols):
			var idx: int = zi * vertex_cols + xi
			var sample: Dictionary = _sample_vertex(
				xi, zi, cols, rows, subdivisions, margin_steps, cell,
				resolved, base_height, level_height, transition_width, outer_margin_cells
			)
			vertices[idx] = sample["p"] as Vector3
			uvs[idx] = sample["uv"] as Vector2

	# 2) Normales par gradient du champ de hauteur. Elles gardent toujours Y > 0.
	for zi in range(vertex_rows):
		for xi in range(vertex_cols):
			var idx: int = zi * vertex_cols + xi
			var left_x: int = maxi(0, xi - 1)
			var right_x: int = mini(vertex_cols - 1, xi + 1)
			var near_z: int = maxi(0, zi - 1)
			var far_z: int = mini(vertex_rows - 1, zi + 1)

			var p_left: Vector3 = vertices[zi * vertex_cols + left_x]
			var p_right: Vector3 = vertices[zi * vertex_cols + right_x]
			var p_near: Vector3 = vertices[near_z * vertex_cols + xi]
			var p_far: Vector3 = vertices[far_z * vertex_cols + xi]

			var tangent_x: Vector3 = p_right - p_left
			var tangent_z: Vector3 = p_far - p_near
			var n: Vector3 = tangent_z.cross(tangent_x).normalized()
			if n.y < 0.0:
				n = -n
			if n.length_squared() < 0.5:
				n = Vector3.UP
			normals[idx] = n

	# 3) Triangles. Le matériau est double-face pour la prévisualisation, donc
	# l'ordre ne peut plus faire disparaître une terrasse.
	indices.resize(x_segments * z_segments * 6)
	var write_index: int = 0
	for zi in range(z_segments):
		for xi in range(x_segments):
			var i00: int = zi * vertex_cols + xi
			var i10: int = i00 + 1
			var i01: int = (zi + 1) * vertex_cols + xi
			var i11: int = i01 + 1
			if ((xi + zi) & 1) == 0:
				indices[write_index] = i00; write_index += 1
				indices[write_index] = i01; write_index += 1
				indices[write_index] = i11; write_index += 1
				indices[write_index] = i00; write_index += 1
				indices[write_index] = i11; write_index += 1
				indices[write_index] = i10; write_index += 1
			else:
				indices[write_index] = i00; write_index += 1
				indices[write_index] = i01; write_index += 1
				indices[write_index] = i10; write_index += 1
				indices[write_index] = i10; write_index += 1
				indices[write_index] = i01; write_index += 1
				indices[write_index] = i11; write_index += 1

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices

	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, material)
	return mesh

static func recommended_subdivisions(total_cells: int) -> int:
	if total_cells <= 225:
		return 8
	if total_cells <= 900:
		return 5
	if total_cells <= 3600:
		return 3
	if total_cells <= 16000:
		return 2
	return 1

static func _sample_vertex(
		x_step: int,
		z_step: int,
		cols: int,
		rows: int,
		subdivisions: int,
		margin_steps: int,
		cell_size: float,
		heights: Array,
		base_height: float,
		level_height: float,
		transition_width: float,
		outer_margin_cells: float
	) -> Dictionary:
	var gx: float = (float(x_step - margin_steps) / float(subdivisions)) - 0.5
	var gz: float = (float(z_step - margin_steps) / float(subdivisions)) - 0.5

	var terrain_height: float = _sample_terraced_height(
		gx, gz, cols, rows, heights, base_height, level_height, transition_width
	)

	# Bord extérieur : une pente continue vers un socle légèrement relevé.
	var edge_distance: float = minf(
		minf(gx + 0.5, (float(cols) - 0.5) - gx),
		minf(gz + 0.5, (float(rows) - 0.5) - gz)
	)
	if edge_distance < 0.0:
		var fade: float = _smootherstep(-outer_margin_cells, 0.0, edge_distance)
		terrain_height = lerpf(0.10, terrain_height, fade)

	var world_x: float = (gx - float(cols - 1) * 0.5) * cell_size
	var world_z: float = (gz - float(rows - 1) * 0.5) * cell_size
	var uv := Vector2(gx + 0.5, gz + 0.5)
	return {"p": Vector3(world_x, terrain_height, world_z), "uv": uv}

static func _sample_terraced_height(
		gx: float,
		gz: float,
		cols: int,
		rows: int,
		heights: Array,
		base_height: float,
		level_height: float,
		transition_width: float
	) -> float:
	var xb: Dictionary = _axis_blend(gx, cols, transition_width)
	var zb: Dictionary = _axis_blend(gz, rows, transition_width)

	var x0: int = int(xb["a"])
	var x1: int = int(xb["b"])
	var z0: int = int(zb["a"])
	var z1: int = int(zb["b"])
	var tx: float = float(xb["t"])
	var tz: float = float(zb["t"])

	var row0: Array = heights[z0] as Array
	var row1: Array = heights[z1] as Array
	var h00: float = _height_for(int(row0[x0]), base_height, level_height)
	var h10: float = _height_for(int(row0[x1]), base_height, level_height)
	var h01: float = _height_for(int(row1[x0]), base_height, level_height)
	var h11: float = _height_for(int(row1[x1]), base_height, level_height)

	var north: float = lerpf(h00, h10, tx)
	var south: float = lerpf(h01, h11, tx)
	return lerpf(north, south, tz)

static func _axis_blend(position: float, count: int, transition_width: float) -> Dictionary:
	var last: int = maxi(0, count - 1)
	if last == 0:
		return {"a": 0, "b": 0, "t": 0.0}
	if position <= 0.0:
		return {"a": 0, "b": 0, "t": 0.0}
	if position >= float(last):
		return {"a": last, "b": last, "t": 0.0}

	var left: int = int(floor(position))
	var frac: float = position - float(left)
	var half_transition: float = transition_width * 0.5
	var start: float = 0.5 - half_transition
	var finish: float = 0.5 + half_transition
	if frac <= start:
		return {"a": left, "b": left, "t": 0.0}
	if frac >= finish:
		return {"a": left + 1, "b": left + 1, "t": 0.0}
	return {"a": left, "b": left + 1, "t": _smootherstep(start, finish, frac)}

static func _resolve_non_significant_zeroes(height_map: Array) -> Array:
	var rows: int = height_map.size()
	var result: Array = []
	for source_row in height_map:
		var row: Array = source_row as Array
		var copy_row: Array[int] = []
		for value in row:
			copy_row.append(int(value))
		result.append(copy_row)

	for _pass_index in range(4):
		var changed: bool = false
		for r in range(rows):
			var current_row: Array = result[r] as Array
			for c in range(current_row.size()):
				if int(current_row[c]) != 0:
					continue
				var values: Array[int] = []
				var directions: Array[Vector2i] = [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
				for d in directions:
					var nr: int = r + d.y
					var nc: int = c + d.x
					if nr >= 0 and nr < rows:
						var neighbor_row: Array = result[nr] as Array
						if nc >= 0 and nc < neighbor_row.size():
							var v: int = int(neighbor_row[nc])
							if v > 0:
								values.append(v)
				if not values.is_empty():
					var total: int = 0
					for v in values:
						total += v
					current_row[c] = clampi(int(round(float(total) / float(values.size()))), MIN_LEVEL, MAX_LEVEL)
					changed = true
		if not changed:
			break

	for r in range(rows):
		var final_row: Array = result[r] as Array
		for c in range(final_row.size()):
			if int(final_row[c]) == 0:
				final_row[c] = MIN_LEVEL
	return result

static func _height_for(level: int, base_height: float, level_height: float) -> float:
	var safe_level: int = clampi(level, MIN_LEVEL, MAX_LEVEL)
	return maxf(0.12, base_height) + float(safe_level - 1) * maxf(0.05, level_height)

static func _smootherstep(edge0: float, edge1: float, x: float) -> float:
	if is_equal_approx(edge0, edge1):
		return 0.0
	var t: float = clampf((x - edge0) / (edge1 - edge0), 0.0, 1.0)
	return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
