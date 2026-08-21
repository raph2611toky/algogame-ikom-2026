extends Control

const INLINE_ELEVATION_HEADERS := ["ELEVATION", "HEIGHTS", "HEIGHT_MAP"]

@onready var game_session: GameSessionService = get_node("/root/GameSession") as GameSessionService

@onready var preview_panel: PanelContainer = $Content/PreviewPanel
@onready var info_panel: PanelContainer = $Content/InfoPanel
@onready var preview: GameBoard = $Content/PreviewPanel/Preview
@onready var file_label: Label = $Content/InfoPanel/Margin/VBox/FileLabel
@onready var elevation_label: Label = $Content/InfoPanel/Margin/VBox/ElevationLabel
@onready var size_label: Label = $Content/InfoPanel/Margin/VBox/SizeLabel
@onready var time_label: Label = $Content/InfoPanel/Margin/VBox/TimeLabel
@onready var objects_label: Label = $Content/InfoPanel/Margin/VBox/ObjectsLabel
@onready var terrain_label: Label = $Content/InfoPanel/Margin/VBox/TerrainLabel
@onready var validation_label: Label = $Content/InfoPanel/Margin/VBox/ValidationLabel
@onready var error_label: Label = $Content/InfoPanel/Margin/VBox/ErrorLabel
@onready var import_button: Button = $Content/InfoPanel/Margin/VBox/ImportButton
@onready var elevation_button: Button = $Content/InfoPanel/Margin/VBox/ElevationButton
@onready var play_button: Button = $Content/InfoPanel/Margin/VBox/PlayButton
@onready var back_button: Button = $Content/InfoPanel/Margin/VBox/BackButton
@onready var file_dialog: FileDialog = $FileDialog
@onready var elevation_dialog: FileDialog = $ElevationFileDialog

var current_data: Dictionary = {}
var current_response: Dictionary = {}
var current_path: String = ""
# Texte strict map.txt envoyé au backend (sans ancienne section ELEVATION inline).
var current_text: String = ""
var current_elevation_path: String = ""
var current_elevation_text: String = ""
var current_elevation_inline: bool = false
var preview_state: GameState
var loading: bool = false

func _ready() -> void:
	UIStyle.apply_panel(preview_panel)
	UIStyle.apply_panel(info_panel)
	UIStyle.apply_button(import_button, 22)
	UIStyle.apply_button(elevation_button, 19)
	UIStyle.apply_button(play_button, 25)
	UIStyle.apply_button(back_button, 22)
	import_button.pressed.connect(func(): file_dialog.popup_centered_ratio(0.78))
	elevation_button.pressed.connect(func(): elevation_dialog.popup_centered_ratio(0.72))
	play_button.pressed.connect(_on_play)
	back_button.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn"))
	file_dialog.file_selected.connect(_on_file_selected)
	elevation_dialog.file_selected.connect(_on_elevation_selected)
	var initial := str(game_session.selected_map_path)
	if initial.is_empty():
		initial = "res://data/maps/demo_simulation/map.txt"
	var remembered_elevation := ""
	if initial == game_session.selected_map_path:
		remembered_elevation = str(game_session.selected_elevation_path)
	await _load_map(initial, remembered_elevation)

func _on_file_selected(path: String) -> void:
	await _load_map(path)

func _on_elevation_selected(path: String) -> void:
	if current_path.is_empty():
		_show_error("Importez d'abord map.txt.")
		return
	await _load_map(current_path, path)

func _load_map(path: String, elevation_override: String = "") -> void:
	if loading:
		return
	loading = true
	play_button.disabled = true
	import_button.disabled = true
	elevation_button.disabled = true
	validation_label.text = "BACKEND V14 • VALIDATION MAP + RELIEF 3D..."
	validation_label.add_theme_color_override("font_color", Color("#e8c57e"))
	error_label.text = ""

	var map_read := _read_text_file(path)
	if not bool(map_read.get("ok", false)):
		_show_error(str(map_read.get("error", "Impossible d'ouvrir map.txt")))
		_finish_loading()
		return

	var prepared := _prepare_backend_map_payload(str(map_read.get("text", "")))
	if not bool(prepared.get("ok", false)):
		_show_error(str(prepared.get("error", "map.txt invalide")))
		_finish_loading()
		return
	current_text = str(prepared.get("map_text", ""))
	var inline_elevation_text := str(prepared.get("elevation_text", ""))

	var elevation_path := elevation_override
	if elevation_path.is_empty():
		elevation_path = _detect_elevation_path(path)
	current_elevation_text = ""
	current_elevation_path = ""
	current_elevation_inline = false
	if not elevation_path.is_empty():
		var elevation_read := _read_text_file(elevation_path)
		if not bool(elevation_read.get("ok", false)):
			_show_error(str(elevation_read.get("error", "Impossible d'ouvrir elevation.txt")))
			_finish_loading()
			return
		current_elevation_path = elevation_path
		current_elevation_text = str(elevation_read.get("text", ""))
	elif not inline_elevation_text.is_empty():
		# Compatibilité avec l'ancien frontend 3D : la section inline est séparée
		# avant l'appel FastAPI car le backend d'évaluation attend deux fichiers.
		current_elevation_text = inline_elevation_text
		current_elevation_inline = true

	var response: Dictionary = await BackendAPI.parse_map_text(
		current_text,
		path.get_file().get_basename(),
		current_elevation_text
	)
	if not bool(response.get("ok", false)):
		_show_error(_api_error(response))
		_finish_loading()
		return

	current_response = response.get("data", {})
	current_data = BackendStateAdapter.map_response_to_game_data(current_response, path, current_text)
	current_path = path
	var has_elevation := bool(current_response.get("has_elevation", false))
	validation_label.text = "✓ BACKEND V14 • MAP + ELEVATION • RENDU 3D COMPATIBLE" if has_elevation else "✓ BACKEND V14 • CARTE PLATE COMPATIBLE"
	validation_label.add_theme_color_override("font_color", Color("#9fdd83"))
	play_button.disabled = false
	file_label.text = "Map : %s" % path.get_file()
	if has_elevation:
		var source_label := "section ELEVATION intégrée" if current_elevation_inline else current_elevation_path.get_file()
		elevation_label.text = "Élévation : %s  •  Z1–Z%d  •  plateau 3D" % [
			source_label,
			int(current_data.get("max_elevation", 0))
		]
		elevation_label.add_theme_color_override("font_color", Color("#d9b66f"))
	else:
		elevation_label.text = "Élévation : aucune • mode plat historique"
		elevation_label.add_theme_color_override("font_color", Color("#b8aea0"))

	size_label.text = "Dimensions : %d × %d • %d cases" % [
		int(current_response.get("width", 0)),
		int(current_response.get("height", 0)),
		int(current_response.get("width", 0)) * int(current_response.get("height", 0))
	]
	time_label.text = "Temps relatif : %d s  •  %d ticks max" % [int(current_response.get("time_limit", 0)), int(current_response.get("time_limit", 0))]
	var counts: Dictionary = current_response.get("counts", {})
	var x_count := 0
	var g_count := 0
	for machine_value in current_response.get("machines", []):
		var machine: Dictionary = machine_value
		if str(machine.get("kind", "")) == "X":
			x_count += 1
		else:
			g_count += 1
	objects_label.text = "Pierres + : %d   •   Coffres * : %d\nExcavateurs X : %d   •   Grapplers G : %d" % [
		int(counts.get("stones", 0)), int(counts.get("chests", 0)), x_count, g_count
	]
	terrain_label.text = "Rochers # : %d   •   Arbres t : %d\nTrous o : %d   •   Cachettes @ : %d" % [
		int(counts.get("rocks", 0)), int(counts.get("trees", 0)), int(counts.get("holes", 0)), int(counts.get("bushes", 0))
	]
	preview_state = GameState.new()
	preview_state.setup(current_data)
	preview.set_state(preview_state, [], 0.0)
	_finish_loading()

func _prepare_backend_map_payload(raw_text: String) -> Dictionary:
	var normalized := raw_text.replace("\r\n", "\n").replace("\r", "\n")
	if normalized.begins_with("\ufeff"):
		normalized = normalized.substr(1)
	var raw_lines := normalized.split("\n", false)
	var lines: Array[String] = []
	for raw_value in raw_lines:
		var line := str(raw_value).strip_edges()
		if not line.is_empty():
			lines.append(line)
	if lines.is_empty():
		return {"ok": false, "error": "map.txt est vide."}
	var header := lines[0].split(" ", false)
	if header.size() != 3 or not str(header[0]).is_valid_int() or not str(header[1]).is_valid_int():
		return {"ok": false, "error": "La première ligne doit être H W TIME_LIMIT."}
	var height := int(header[0])
	var width := int(header[1])
	if height <= 0 or width <= 0 or lines.size() < height + 1:
		return {"ok": false, "error": "map.txt ne contient pas toutes les lignes annoncées."}
	var map_lines: Array[String] = [lines[0]]
	for row_index in range(height):
		map_lines.append(lines[row_index + 1])
	var elevation_text := ""
	var marker_index := height + 1
	if lines.size() > marker_index and INLINE_ELEVATION_HEADERS.has(lines[marker_index].to_upper()):
		if lines.size() < marker_index + 1 + height:
			return {"ok": false, "error": "La section ELEVATION inline est incomplète."}
		var elevation_lines: Array[String] = []
		for row_index in range(height):
			var raw_height := lines[marker_index + 1 + row_index]
			var tokens := raw_height.split(" ", false)
			var compact := raw_height
			if tokens.size() == width:
				compact = "".join(tokens)
			# L'ancien renderer 3D pouvait attribuer une hauteur visuelle aux rochers.
			# Le contrat Addendum/V14 impose 0 dans elevation.txt pour '#'.
			if compact.length() == width:
				var normalized_height := PackedStringArray()
				var map_row := map_lines[row_index + 1]
				for col_index in range(width):
					normalized_height.append("0" if map_row.substr(col_index, 1) == "#" else compact.substr(col_index, 1))
				compact = "".join(normalized_height)
			elevation_lines.append(compact)
		elevation_text = "\n".join(elevation_lines)
	return {
		"ok": true,
		"map_text": "\n".join(map_lines),
		"elevation_text": elevation_text,
	}

func _detect_elevation_path(map_path: String) -> String:
	var directory := map_path.get_base_dir()
	var base_name := map_path.get_file().get_basename()
	var candidates: Array[String] = [
		directory.path_join("%s_elevation.txt" % base_name),
		directory.path_join("%s.elevation.txt" % base_name),
		directory.path_join("elevation.txt"),
	]
	if base_name.ends_with("_map"):
		candidates.append(directory.path_join("%s_elevation.txt" % base_name.trim_suffix("_map")))
	for candidate in candidates:
		if FileAccess.file_exists(candidate):
			return candidate
	return ""

func _read_text_file(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {"ok": false, "error": "Impossible d'ouvrir : %s" % path, "text": ""}
	var text := file.get_as_text()
	file.close()
	return {"ok": true, "error": "", "text": text}

func _finish_loading() -> void:
	loading = false
	import_button.disabled = false
	elevation_button.disabled = current_path.is_empty() and current_data.is_empty()

func _show_error(message: String) -> void:
	current_data = {}
	current_response = {}
	error_label.text = "✖ %s" % message
	validation_label.text = "BACKEND / CARTE / ÉLÉVATION INDISPONIBLE"
	validation_label.add_theme_color_override("font_color", Color("#ff7566"))
	play_button.disabled = true

func _api_error(response: Dictionary) -> String:
	var message := str(response.get("error", "Erreur backend inconnue"))
	if int(response.get("status", 0)) == 0:
		return "%s\nVérifiez que FastAPI V14 tourne sur %s." % [message, BackendAPI.endpoint_label()]
	return message

func _on_play() -> void:
	if current_data.is_empty() or current_text.is_empty():
		return
	game_session.set_selected_map(
		current_path,
		current_data,
		current_text,
		current_response,
		current_elevation_path,
		current_elevation_text
	)
	get_tree().change_scene_to_file("res://scenes/menu/MissionLaunch.tscn")
