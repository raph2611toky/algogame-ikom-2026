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
var current_path: String = ""
var preview_state: GameState

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

	var initial: String = String(game_session.selected_map_path)
	if initial.is_empty():
		initial = "res://data/maps/example_map.txt"
	_load_map(initial)

func _on_file_selected(path: String) -> void:
	_load_map(path)

func _load_map(path: String) -> void:
	var result: Dictionary = MapLoader.load_from_file(path)
	if not bool(result.get("ok", false)):
		current_data = {}
		current_path = ""
		error_label.text = "✖ %s" % String(result.get("error", "Erreur inconnue"))
		validation_label.text = "CARTE INVALIDE"
		validation_label.add_theme_color_override("font_color", Color("#ff7566"))
		play_button.disabled = true
		return

	current_data = result["data"]
	current_path = path
	error_label.text = ""
	validation_label.text = "✓ CARTE VALIDE • PRÊTE À SIMULER"
	validation_label.add_theme_color_override("font_color", Color("#9fdd83"))
	play_button.disabled = false
	file_label.text = "Fichier : %s" % path.get_file()
	size_label.text = "Dimensions : %d × %d cellules" % [int(current_data["width"]), int(current_data["height"])]
	time_label.text = "Temps relatif : %d s  •  %d ticks max" % [int(current_data["time_limit"]), int(current_data["time_limit"])]
	var x_count: int = 0
	var g_count: int = 0
	for machine_value in current_data["machines"]:
		var machine: Dictionary = machine_value
		if String(machine["kind"]) == "X":
			x_count += 1
		else:
			g_count += 1
	objects_label.text = "Pierres + : %d   •   Coffres * : %d\nExcavateurs X : %d   •   Grapplers G : %d" % [
		current_data["stones"].size(), current_data["chests"].size(), x_count, g_count
	]
	var terrain_counts: Dictionary = current_data.get("terrain_counts", {})
	terrain_label.text = "Rochers # : %d   •   Arbres t : %d\nTrous o : %d   •   Cachettes @ : %d" % [
		int(terrain_counts.get("#", 0)), int(terrain_counts.get("t", 0)),
		int(terrain_counts.get("o", 0)), int(terrain_counts.get("@", 0))
	]
	preview_state = GameState.new()
	preview_state.setup(current_data)
	preview.set_state(preview_state, [], 0.0)

func _on_play() -> void:
	if current_data.is_empty():
		return
	game_session.set_selected_map(current_path, current_data)
	get_tree().change_scene_to_file("res://scenes/menu/MissionLaunch.tscn")
