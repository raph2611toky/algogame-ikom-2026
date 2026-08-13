extends Control

@onready var game_session: GameSessionService = get_node("/root/GameSession") as GameSessionService

@onready var panel: PanelContainer = $Panel
@onready var score_label: Label = $Panel/Margin/VBox/Score
@onready var breakdown: Label = $Panel/Margin/VBox/Breakdown
@onready var path_label: Label = $Panel/Margin/VBox/Path
@onready var actions_preview: TextEdit = $Panel/Margin/VBox/ActionsPreview
@onready var replay_button: Button = $Panel/Margin/VBox/Buttons/ReplayButton
@onready var maps_button: Button = $Panel/Margin/VBox/Buttons/MapsButton
@onready var export_button: Button = $Panel/Margin/VBox/Buttons/ExportButton
@onready var folder_button: Button = $Panel/Margin/VBox/Buttons/FolderButton
@onready var menu_button: Button = $Panel/Margin/VBox/Buttons/MenuButton
@onready var export_dialog: FileDialog = $ExportDialog

func _ready() -> void:
	UIStyle.apply_panel(panel)
	for button in [replay_button, maps_button, export_button, folder_button, menu_button]:
		UIStyle.apply_button(button, 18)
	replay_button.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/game/GameScreen.tscn"))
	maps_button.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/menu/MissionSelect.tscn"))
	menu_button.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn"))
	folder_button.pressed.connect(_open_actions_folder)
	export_button.pressed.connect(func(): export_dialog.popup_centered_ratio(0.72))
	export_dialog.file_selected.connect(_export_actions)
	_show_result()

func _show_result() -> void:
	var s: Dictionary = game_session.last_summary
	if s.is_empty():
		score_label.text = "SCORE : -"
		breakdown.text = "Aucun résultat disponible."
		actions_preview.text = ""
		return
	var ratio: float = float(s.get("completion_ratio", 0.0)) * 100.0
	score_label.text = "SCORE FINAL  •  %d" % int(s["score"])
	breakdown.text = "COFFRES  %d/%d  → +%d pts     PIERRES  %d/%d  → +%d pts\nRESSOURCES RESTANTES → +%d pts     TEMPS RESTANT %d s → +%d pts\nSTA F %d / M %d     BAT F %d / M %d     OBJECTIFS %.0f%%\nTicks exécutés : %d     Fin : %s" % [
		int(s["hidden_chests"]), int(s["total_chests"]), int(s.get("chest_points", 0)),
		int(s["collected_stones"]), int(s["total_stones"]), int(s.get("stone_points", 0)),
		int(s.get("resource_points", 0)), int(s["remaining_time"]), int(s.get("time_points", 0)),
		int(s["stamina_f"]), int(s["stamina_m"]), int(s["battery_f"]), int(s["battery_m"]), ratio,
		int(s["ticks"]), String(s["end_reason"])
	]
	path_label.text = "actions.txt : %s" % game_session.last_actions_path
	actions_preview.text = ActionsWriter.read_text(game_session.last_actions_path)

func _export_actions(path: String) -> void:
	if path.get_extension().to_lower() != "txt":
		path += ".txt"
	var ok: bool = ActionsWriter.export_existing(game_session.last_actions_path, path)
	path_label.text = "Exporté : %s" % path if ok else "Erreur pendant l'export de actions.txt"

func _open_actions_folder() -> void:
	if game_session.last_actions_path.is_empty():
		return
	OS.shell_open(game_session.last_actions_path.get_base_dir())
