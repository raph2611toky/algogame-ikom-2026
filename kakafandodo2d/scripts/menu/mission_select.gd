extends Control

@onready var game_session: GameSessionService = get_node("/root/GameSession") as GameSessionService

@onready var preview_panel: PanelContainer = $Content/PreviewPanel
@onready var info_panel: PanelContainer = $Content/InfoPanel
@onready var preview: GameBoard = $Content/PreviewPanel/Preview
@onready var file_label: Label = $Content/InfoPanel/Margin/VBox/FileLabel
@onready var size_label: Label = $Content/InfoPanel/Margin/VBox/SizeLabel
@onready var time_label: Label = $Content/InfoPanel/Margin/VBox/TimeLabel
@onready var objects_label: Label = $Content/InfoPanel/Margin/VBox/ObjectsLabel
@onready var terrain_label: Label = $Content/InfoPanel/Margin/VBox/TerrainLabel
@onready var validation_label: Label = $Content/InfoPanel/Margin/VBox/ValidationLabel
@onready var error_label: Label = $Content/InfoPanel/Margin/VBox/ErrorLabel
@onready var import_button: Button = $Content/InfoPanel/Margin/VBox/ImportButton
@onready var play_button: Button = $Content/InfoPanel/Margin/VBox/PlayButton
@onready var back_button: Button = $Content/InfoPanel/Margin/VBox/BackButton
@onready var file_dialog: FileDialog = $FileDialog

var current_data: Dictionary = {}
var current_response: Dictionary = {}
var current_path: String = ""
var current_text: String = ""
var preview_state: GameState
var loading: bool = false

func _ready() -> void:
	UIStyle.apply_panel(preview_panel)
	UIStyle.apply_panel(info_panel)
	UIStyle.apply_button(import_button, 23)
	UIStyle.apply_button(play_button, 25)
	UIStyle.apply_button(back_button, 22)
	import_button.pressed.connect(func(): file_dialog.popup_centered_ratio(0.78))
	play_button.pressed.connect(_on_play)
	back_button.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn"))
	file_dialog.file_selected.connect(_on_file_selected)
	var initial := str(game_session.selected_map_path)
	if initial.is_empty():
		initial = "res://data/maps/example_map.txt"
	await _load_map(initial)

func _on_file_selected(path: String) -> void:
	await _load_map(path)

func _load_map(path: String) -> void:
	if loading:
		return
	loading = true
	play_button.disabled = true
	import_button.disabled = true
	validation_label.text = "CONNEXION BACKEND • VALIDATION..."
	validation_label.add_theme_color_override("font_color", Color("#e8c57e"))
	error_label.text = ""
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_show_error("Impossible d'ouvrir le fichier : %s" % path)
		loading = false
		import_button.disabled = false
		return
	current_text = file.get_as_text()
	file.close()
	var response: Dictionary = await BackendAPI.parse_map_file(path)
	if not bool(response.get("ok", false)):
		_show_error(_api_error(response))
		loading = false
		import_button.disabled = false
		return
	current_response = response.get("data", {})
	current_data = BackendStateAdapter.map_response_to_game_data(current_response, path, current_text)
	current_path = path
	validation_label.text = "✓ BACKEND CONNECTÉ • CARTE VALIDE"
	validation_label.add_theme_color_override("font_color", Color("#9fdd83"))
	play_button.disabled = false
	import_button.disabled = false
	file_label.text = "Fichier : %s" % path.get_file()
	size_label.text = "Dimensions : %d × %d cellules" % [int(current_response.get("width", 0)), int(current_response.get("height", 0))]
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
	loading = false

func _show_error(message: String) -> void:
	current_data = {}
	current_response = {}
	current_path = ""
	error_label.text = "✖ %s" % message
	validation_label.text = "BACKEND / CARTE INDISPONIBLE"
	validation_label.add_theme_color_override("font_color", Color("#ff7566"))
	play_button.disabled = true

func _api_error(response: Dictionary) -> String:
	var message := str(response.get("error", "Erreur backend inconnue"))
	if int(response.get("status", 0)) == 0:
		return "%s\nVérifiez que FastAPI tourne sur %s." % [message, BackendAPI.endpoint_label()]
	return message

func _on_play() -> void:
	if current_data.is_empty() or current_text.is_empty():
		return
	game_session.set_selected_map(current_path, current_data, current_text, current_response)
	get_tree().change_scene_to_file("res://scenes/menu/MissionLaunch.tscn")
