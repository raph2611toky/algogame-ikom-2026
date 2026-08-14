extends Control

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
	objectives_label.text = "OBJECTIF\nRécupérer un maximum de pierres précieuses et cacher un maximum de coffres.\n\nAGENTS\nIkotofosa [F] • Imahaki [M]\n\nMOTEUR\nFastAPI %s • stratégie %s" % [BackendAPI.endpoint_label(), str(game_session.get_strategy_options().get("name", "portfolio_v7"))]
	countdown_label.text = "CALCUL IA..."
	countdown_label.add_theme_font_size_override("font_size", 46)
	var strategy := game_session.get_strategy_options()
	var mission_name := str(game_session.selected_map_path).get_file().get_basename()
	var submit: Dictionary = await BackendAPI.submit_simulation_job(
		game_session.selected_map_text,
		mission_name,
		strategy
	)
	if _cancelled:
		return
	if not bool(submit.get("ok", false)):
		countdown_label.text = "ERREUR BACKEND\n%s" % str(submit.get("error", "Impossible de démarrer le calcul"))
		countdown_label.add_theme_font_size_override("font_size", 28)
		return
	var job_payload: Dictionary = submit.get("data", {})
	var job_id := str(job_payload.get("job_id", ""))
	if job_id.is_empty():
		countdown_label.text = "ERREUR BACKEND\njob_id manquant"
		return
	while not _cancelled:
		var status_response: Dictionary = await BackendAPI.get_simulation_job(job_id)
		if not bool(status_response.get("ok", false)):
			countdown_label.text = "ERREUR BACKEND\n%s" % str(status_response.get("error", "Statut du calcul indisponible"))
			countdown_label.add_theme_font_size_override("font_size", 28)
			return
		var job: Dictionary = status_response.get("data", {})
		var job_status := str(job.get("status", ""))
		var elapsed := float(job.get("elapsed_seconds", 0.0))
		countdown_label.text = "CALCUL IA...\n%s • %.1f s" % [str(strategy.get("name", "portfolio_v7")), elapsed]
		if job_status == "completed":
			break
		if job_status == "failed":
			countdown_label.text = "ERREUR STRATÉGIE\n%s" % str(job.get("error", "Calcul impossible"))
			countdown_label.add_theme_font_size_override("font_size", 26)
			return
		await get_tree().create_timer(0.35).timeout
	if _cancelled:
		return
	var result_response: Dictionary = await BackendAPI.get_simulation_job_result(job_id)
	if not bool(result_response.get("ok", false)):
		countdown_label.text = "ERREUR BACKEND\n%s" % str(result_response.get("error", "Résultat de simulation indisponible"))
		countdown_label.add_theme_font_size_override("font_size", 28)
		return
	var result_payload: Dictionary = result_response.get("data", {})
	var simulation_data: Variant = result_payload.get("simulation", {})
	if not (simulation_data is Dictionary):
		countdown_label.text = "ERREUR BACKEND\nSimulation invalide"
		return
	game_session.set_simulation(simulation_data)
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
