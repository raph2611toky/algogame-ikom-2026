extends Control

const STEP1_BOARD_CAMERA_ONLY := false

@onready var game_session: GameSessionService = get_node("/root/GameSession") as GameSessionService
@onready var preview: GameBoard = $Content/Panel/Margin/VBox/Preview
@onready var map_label: Label = $Content/Panel/Margin/VBox/Header/MapLabel
@onready var objectives_label: Label = $Content/Panel/Margin/VBox/Briefing/Objectives
@onready var countdown_label: Label = $CountdownLayer/Countdown
@onready var cancel_button: Button = $Content/Panel/Margin/VBox/Buttons/CancelButton

var _audio: GameAudio
var _cancelled: bool = false

func _ready() -> void:
	_audio = GameAudio.new()
	add_child(_audio)
	UIStyle.apply_panel($Content/Panel)
	UIStyle.apply_button(cancel_button, 20)
	cancel_button.pressed.connect(_cancel)
	var data: Dictionary = game_session.selected_map_data
	if data.is_empty() or game_session.selected_map_text.is_empty():
		countdown_label.text = "MISSION NON CHARGÉE"
		return
	var preview_state := GameState.new()
	preview_state.setup(data)
	preview.set_state(preview_state, [], 0.0)
	map_label.text = "%s  •  %d×%d  •  %d s" % [
		str(game_session.selected_map_path).get_file(),
		int(data["width"]), int(data["height"]), int(data["time_limit"])
	]
	var elevation_note := "Z1 • ponts/rampes prêts"
	if bool(data.get("has_explicit_elevation", false)):
		elevation_note = "Z1 → Z%d • élévation active • pont si ΔZ=1" % maxi(1, int(data.get("max_elevation", 1)))
	objectives_label.text = "SIMULATION LOCALE DYNAMIQUE\nIA des héros + routines machines + élévation + score.\n\nMAP\n%d × %d • %d ticks maximum.\n\nRYTHME\n1 tick relatif = 0,2 s réel • %s" % [int(data["width"]), int(data["height"]), int(data["time_limit"]), elevation_note]
	if STEP1_BOARD_CAMERA_ONLY:
		countdown_label.text = "PLATEAU 3D"
		countdown_label.add_theme_font_size_override("font_size", 54)
		await get_tree().create_timer(0.20).timeout
		if not _cancelled:
			get_tree().change_scene_to_file("res://scenes/game/GameScreen.tscn")
		return

	countdown_label.text = "CALCUL LOCAL..."
	countdown_label.add_theme_font_size_override("font_size", 54)
	await get_tree().process_frame
	var local_simulation: Dictionary = LocalSimulationRunner.run(
		data,
		str(game_session.selected_map_path).get_file().get_basename()
	)
	if _cancelled:
		return
	if local_simulation.is_empty():
		countdown_label.text = "ERREUR SIMULATION LOCALE"
		countdown_label.add_theme_font_size_override("font_size", 30)
		return
	game_session.set_simulation(local_simulation)
	_audio.play_mission_start()
	await get_tree().create_timer(0.25).timeout
	_start_countdown()

func _start_countdown() -> void:
	countdown_label.add_theme_font_size_override("font_size", 108)
	for value in [3, 2, 1]:
		if _cancelled:
			return
		countdown_label.text = str(value)
		countdown_label.modulate.a = 0.0
		countdown_label.scale = Vector2(1.45, 1.45)
		countdown_label.pivot_offset = countdown_label.size / 2.0
		var tween := create_tween()
		tween.set_trans(Tween.TRANS_BACK)
		tween.set_ease(Tween.EASE_OUT)
		tween.tween_property(countdown_label, "modulate:a", 1.0, 0.10)
		tween.parallel().tween_property(countdown_label, "scale", Vector2.ONE, 0.18)
		await get_tree().create_timer(0.62).timeout
	if _cancelled:
		return
	countdown_label.text = "GO !"
	countdown_label.modulate = Color("#ffe08a")
	var go_tween := create_tween()
	go_tween.set_trans(Tween.TRANS_BACK)
	go_tween.set_ease(Tween.EASE_OUT)
	go_tween.tween_property(countdown_label, "scale", Vector2(1.18, 1.18), 0.12)
	go_tween.tween_property(countdown_label, "scale", Vector2.ONE, 0.12)
	await get_tree().create_timer(0.35).timeout
	get_tree().change_scene_to_file("res://scenes/game/GameScreen.tscn")

func _cancel() -> void:
	_cancelled = true
	_audio.play_ui_click()
	get_tree().change_scene_to_file("res://scenes/menu/MissionSelect.tscn")
