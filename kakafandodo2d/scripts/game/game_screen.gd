extends Control

@onready var game_session: GameSessionService = get_node("/root/GameSession") as GameSessionService

const RELATIVE_TICK_REAL_SECONDS := 0.2

@onready var board_panel: PanelContainer = $BoardPanel
@onready var board: GameBoard = $BoardPanel/Board
@onready var f_panel: PanelContainer = $TopLayer/FPanel
@onready var m_panel: PanelContainer = $TopLayer/MPanel
@onready var center_panel: PanelContainer = $TopLayer/CenterPanel
@onready var objectives_panel: PanelContainer = $TopLayer/ObjectivesPanel
@onready var playback_panel: PanelContainer = $TopLayer/PlaybackPanel
@onready var quick_settings: PanelContainer = $TopLayer/QuickSettings

@onready var f_stamina: ProgressBar = $TopLayer/FPanel/Margin/HBox/VBox/Stamina
@onready var f_battery: ProgressBar = $TopLayer/FPanel/Margin/HBox/VBox/Battery
@onready var f_info: Label = $TopLayer/FPanel/Margin/HBox/VBox/Info
@onready var m_stamina: ProgressBar = $TopLayer/MPanel/Margin/HBox/VBox/Stamina
@onready var m_battery: ProgressBar = $TopLayer/MPanel/Margin/HBox/VBox/Battery
@onready var m_info: Label = $TopLayer/MPanel/Margin/HBox/VBox/Info

@onready var time_label: Label = $TopLayer/CenterPanel/VBox/Stats/Time
@onready var score_label: Label = $TopLayer/CenterPanel/VBox/Stats/Score
@onready var tick_label: Label = $TopLayer/CenterPanel/VBox/Stats/Tick
@onready var objectives_label: Label = $TopLayer/ObjectivesPanel/Label
@onready var status_label: Label = $TopLayer/StatusLabel
@onready var event_banner: Label = $TopLayer/EventBanner
@onready var effect_flash: ColorRect = $TopLayer/EffectFlash

@onready var settings_button: Button = $TopLayer/SettingsButton
@onready var pause_button: Button = $TopLayer/PlaybackPanel/HBox/PauseButton
@onready var play_button: Button = $TopLayer/PlaybackPanel/HBox/PlayButton
@onready var speed_button: Button = $TopLayer/PlaybackPanel/HBox/SpeedButton
@onready var speed_label: Label = $TopLayer/PlaybackPanel/HBox/SpeedLabel
@onready var last_actions: Label = $TopLayer/PlaybackPanel/HBox/LastActions

@onready var quick_sound: HSlider = $TopLayer/QuickSettings/Margin/VBox/Sound
@onready var quick_music: HSlider = $TopLayer/QuickSettings/Margin/VBox/Music
@onready var quick_effects: HSlider = $TopLayer/QuickSettings/Margin/VBox/Effects
@onready var quick_close: Button = $TopLayer/QuickSettings/Margin/VBox/Buttons/CloseButton
@onready var quick_menu: Button = $TopLayer/QuickSettings/Margin/VBox/Buttons/MenuButton

var playback_state: GameState
var simulation_data: Dictionary = {}
var simulation_ticks: Array = []
var tick_index: int = 0
var accumulator: float = 0.0
var playback_speed: float = 1.0
var paused: bool = false
var finishing: bool = false
var paused_before_settings: bool = false
var audio: GameAudio
var camera_tween: Tween
var board_panel_rest_position: Vector2 = Vector2.ZERO
var previous_score: int = -1
var previous_stones: int = -1
var previous_chests: int = -1

func _ready() -> void:
	audio = GameAudio.new()
	add_child(audio)
	_style_ui()
	pause_button.pressed.connect(_pause_simulation)
	play_button.pressed.connect(_resume_simulation)
	speed_button.pressed.connect(_cycle_speed)
	settings_button.pressed.connect(_open_quick_settings)
	quick_close.pressed.connect(_close_quick_settings)
	quick_menu.pressed.connect(_return_to_menu)
	quick_sound.value_changed.connect(_on_quick_sound_changed)
	quick_music.value_changed.connect(_on_quick_music_changed)
	quick_effects.value_changed.connect(_on_quick_effects_changed)
	_load_quick_settings()
	board.set_effects_percent(int(game_session.settings["effects"]))

	if not game_session.has_simulation():
		status_label.text = "ERREUR BACKEND : aucune simulation calculée."
		set_process(false)
		return
	simulation_data = game_session.simulation
	simulation_ticks = simulation_data.get("ticks", [])
	tick_index = 0
	playback_state = BackendStateAdapter.create_state(
		simulation_data,
		simulation_data.get("initial_state", {}),
		game_session.selected_map_path
	)
	board.set_state(playback_state, [], 0.0)
	_update_hud({"F": "WAIT", "M": "WAIT"})
	status_label.text = "FASTAPI • %s • %d ticks calculés • 0,2 s/tick" % [str(game_session.selected_map_path).get_file(), simulation_ticks.size()]
	call_deferred("_setup_camera_rest")
	_show_event_banner("MISSION EN COURS", Color("#ffe1a0"), 0.85)

func _process(delta: float) -> void:
	if paused or finishing or playback_state == null:
		return
	accumulator += delta * playback_speed
	while accumulator >= RELATIVE_TICK_REAL_SECONDS:
		accumulator -= RELATIVE_TICK_REAL_SECONDS
		if tick_index >= simulation_ticks.size():
			_finish_game()
			break
		var tick_data: Dictionary = simulation_ticks[tick_index]
		var actions: Dictionary = tick_data.get("effective_actions", {"F": "WAIT", "M": "WAIT"})
		BackendStateAdapter.apply_snapshot(playback_state, tick_data.get("state", {}), actions)
		var events: Array = BackendStateAdapter.events_to_frontend(tick_data.get("events", []))
		var animation_duration := clampf(0.14 / playback_speed, 0.035, 0.14)
		board.set_state(playback_state, events, animation_duration)
		audio.play_events(events)
		_camera_react(events)
		_update_hud(actions)
		status_label.text = _event_summary(events)
		_react_to_events(events)
		tick_index += 1
		if tick_index >= simulation_ticks.size():
			_finish_game()
			break

func _style_ui() -> void:
	for panel in [board_panel, f_panel, m_panel, center_panel, objectives_panel, playback_panel, quick_settings]:
		UIStyle.apply_panel(panel)
	UIStyle.apply_progress(f_stamina, Color("#b84536"))
	UIStyle.apply_progress(m_stamina, Color("#b84536"))
	UIStyle.apply_progress(f_battery, Color("#2e9cd0"))
	UIStyle.apply_progress(m_battery, Color("#2e9cd0"))
	UIStyle.apply_button(settings_button, 28)
	UIStyle.apply_button(pause_button, 25)
	UIStyle.apply_button(play_button, 25)
	UIStyle.apply_button(speed_button, 25)
	UIStyle.apply_button(quick_close, 18)
	UIStyle.apply_button(quick_menu, 18)

func _update_hud(actions: Dictionary) -> void:
	var hero_f: Dictionary = playback_state.heroes["F"]
	var hero_m: Dictionary = playback_state.heroes["M"]
	f_stamina.value = int(hero_f["stamina"])
	f_battery.value = int(hero_f["battery"])
	m_stamina.value = int(hero_m["stamina"])
	m_battery.value = int(hero_m["battery"])
	var pos_f: Vector2i = hero_f["pos"]
	var pos_m: Vector2i = hero_m["pos"]
	var hack_f: String = str(hero_f.get("hacking_machine", ""))
	var hack_m: String = str(hero_m.get("hacking_machine", ""))
	var hack_text_f: String = " • HACK %s" % hack_f if not hack_f.is_empty() else ""
	var hack_text_m: String = " • HACK %s" % hack_m if not hack_m.is_empty() else ""
	f_info.text = "STA %d • BAT %d • (%d,%d) • %s%s" % [
		int(hero_f["stamina"]), int(hero_f["battery"]), pos_f.y, pos_f.x, actions.get("F", "WAIT"), hack_text_f
	]
	m_info.text = "STA %d • BAT %d • (%d,%d) • %s%s" % [
		int(hero_m["stamina"]), int(hero_m["battery"]), pos_m.y, pos_m.x, actions.get("M", "WAIT"), hack_text_m
	]
	time_label.text = "◷ %d" % playback_state.remaining_time
	score_label.text = "★ %d" % playback_state.score()
	tick_label.text = "TICK %d" % playback_state.tick
	objectives_label.text = "◆ PIERRES %d/%d\n▣ COFFRES %d/%d" % [
		playback_state.collected_stones,
		playback_state.total_stones,
		playback_state.hidden_chests,
		playback_state.total_chests
	]
	last_actions.text = "F %s | M %s" % [actions.get("F", "WAIT"), actions.get("M", "WAIT")]
	var current_score: int = playback_state.score()
	if previous_score >= 0 and current_score > previous_score:
		_pulse_control(score_label, Color("#ffd766"))
	if previous_stones >= 0 and playback_state.collected_stones > previous_stones:
		_pulse_control(objectives_label, Color("#7fe7ff"))
	if previous_chests >= 0 and playback_state.hidden_chests > previous_chests:
		_pulse_control(objectives_label, Color("#9ee17d"))
	previous_score = current_score
	previous_stones = playback_state.collected_stones
	previous_chests = playback_state.hidden_chests

func _event_summary(events: Array) -> String:
	if events.is_empty():
		return "Aucune modification visible sur ce tick."
	var messages: Array[String] = []
	for event_data in events:
		var event_type := str(event_data.get("type", ""))
		match event_type:
			"stone_pickup":
				messages.append("%s récupère %d pierre(s)" % [event_data.get("id", "?"), int(event_data.get("count", 0))])
			"stone_steal":
				messages.append("%s récupère les pierres d'une machine" % event_data.get("id", "?"))
			"chest_hidden":
				messages.append("coffre caché")
			"chest_lost":
				messages.append("coffre perdu dans un trou")
			"cut":
				messages.append("arbre coupé")
			"fill":
				messages.append("trou comblé")
			"dig":
				messages.append("nouveau trou creusé")
			"hack":
				messages.append("%s hacke %s" % [event_data.get("id", "?"), event_data.get("machine", "?")])
			"rotate":
				messages.append("%s tourne %s" % [event_data.get("id", "?"), event_data.get("orientation", "?")])
			"machine_move_queued":
				messages.append("%s prépare MOVE" % event_data.get("id", "?"))
			"machine_blocked":
				messages.append("%s est bloqué" % event_data.get("id", "?"))
			"stamina_recover":
				messages.append("%s récupère de la stamina" % event_data.get("id", "?"))
			"invalid_action":
				messages.append("%s → WAIT (action invalide)" % event_data.get("id", "?"))
			_:
				pass
		if messages.size() >= 3:
			break
	return " • ".join(messages) if not messages.is_empty() else "Simulation en cours • états et déplacements synchronisés"

func _pause_simulation() -> void:
	audio.play_ui_click()
	paused = true
	status_label.text = "SIMULATION EN PAUSE"

func _resume_simulation() -> void:
	audio.play_ui_click()
	if quick_settings.visible:
		return
	paused = false
	status_label.text = "SIMULATION EN COURS"

func _cycle_speed() -> void:
	audio.play_ui_click()
	if playback_speed < 1.5:
		playback_speed = 2.0
	elif playback_speed < 3.0:
		playback_speed = 4.0
	else:
		playback_speed = 1.0
	speed_label.text = "x%d" % int(playback_speed)

func _open_quick_settings() -> void:
	audio.play_ui_click()
	paused_before_settings = paused
	paused = true
	_load_quick_settings()
	quick_settings.visible = true

func _close_quick_settings() -> void:
	audio.play_ui_click()
	quick_settings.visible = false
	paused = paused_before_settings

func _load_quick_settings() -> void:
	quick_sound.set_value_no_signal(int(game_session.settings["sound"]))
	quick_music.set_value_no_signal(int(game_session.settings["music"]))
	quick_effects.set_value_no_signal(int(game_session.settings["effects"]))

func _on_quick_sound_changed(value: float) -> void:
	game_session.settings["sound"] = int(value)
	game_session.apply_settings()
	game_session.save_settings()

func _on_quick_music_changed(value: float) -> void:
	game_session.settings["music"] = int(value)
	game_session.apply_settings()
	game_session.save_settings()

func _on_quick_effects_changed(value: float) -> void:
	game_session.settings["effects"] = int(value)
	board.set_effects_percent(int(value))
	game_session.apply_settings()
	game_session.save_settings()

func _return_to_menu() -> void:
	audio.play_ui_click()
	get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn")

func _setup_camera_rest() -> void:
	board_panel_rest_position = board_panel.position
	board_panel.pivot_offset = board_panel.size * 0.5

func _camera_react(events: Array) -> void:
	if events.is_empty():
		return
	var focus_cell := Vector2i(-1, -1)
	var intensity: float = 0.0
	var priority_types: Array[String] = ["chest_hidden", "chest_lost", "hack", "dig", "cut", "fill", "stone_pickup", "stone_steal", "invalid_action"]
	for wanted_type in priority_types:
		for event_value in events:
			var event_data: Dictionary = event_value
			if str(event_data.get("type", "")) != wanted_type:
				continue
			focus_cell = _screen_event_cell(event_data)
			match wanted_type:
				"chest_hidden", "chest_lost": intensity = 1.0
				"hack", "dig", "cut": intensity = 0.82
				"fill", "stone_pickup", "stone_steal": intensity = 0.62
				_: intensity = 0.45
			break
		if focus_cell.x >= 0:
			break
	if focus_cell.x < 0:
		return

	if camera_tween != null and camera_tween.is_valid():
		camera_tween.kill()
	board_panel.pivot_offset = board_panel.size * 0.5
	var local_point: Vector2 = board.cell_center_local(focus_cell)
	var delta_from_center: Vector2 = local_point - board.size * 0.5
	var safe_size := Vector2(maxf(1.0, board.size.x), maxf(1.0, board.size.y))
	var normalized := Vector2(delta_from_center.x / safe_size.x, delta_from_center.y / safe_size.y)
	var focus_offset := -normalized * Vector2(24.0, 14.0) * intensity
	var zoom_value: float = 1.0 + 0.022 * intensity
	camera_tween = create_tween()
	camera_tween.set_trans(Tween.TRANS_QUAD)
	camera_tween.set_ease(Tween.EASE_OUT)
	camera_tween.tween_property(board_panel, "scale", Vector2(zoom_value, zoom_value), 0.08)
	camera_tween.parallel().tween_property(board_panel, "position", board_panel_rest_position + focus_offset, 0.08)
	camera_tween.tween_interval(0.07)
	camera_tween.tween_property(board_panel, "scale", Vector2.ONE, 0.18)
	camera_tween.parallel().tween_property(board_panel, "position", board_panel_rest_position, 0.18)

func _screen_event_cell(event_data: Dictionary) -> Vector2i:
	if event_data.has("pos"):
		return Vector2i(event_data["pos"])
	if event_data.has("to"):
		return Vector2i(event_data["to"])
	var id: String = str(event_data.get("id", ""))
	if playback_state.heroes.has(id):
		return Vector2i(playback_state.heroes[id]["pos"])
	if playback_state.machines.has(id):
		return Vector2i(playback_state.machines[id]["pos"])
	var machine_id: String = str(event_data.get("machine", ""))
	if playback_state.machines.has(machine_id):
		return Vector2i(playback_state.machines[machine_id]["pos"])
	return Vector2i(-1, -1)

func _react_to_events(events: Array) -> void:
	for event_value in events:
		var event_data: Dictionary = event_value
		var event_type: String = str(event_data.get("type", ""))
		match event_type:
			"hack":
				_flash_screen(Color(0.20, 0.78, 1.0, 0.15))
				_show_event_banner("HACK MACHINE", Color("#8eeeff"), 0.38)
			"chest_hidden":
				_flash_screen(Color(0.45, 0.90, 0.35, 0.14))
				_show_event_banner("TRÉSOR CACHÉ !", Color("#a9ec88"), 0.48)
			"chest_lost":
				_flash_screen(Color(0.75, 0.24, 0.14, 0.13))
				_show_event_banner("COFFRE PERDU", Color("#f0a078"), 0.45)
			"stone_pickup", "stone_steal":
				_show_event_banner("PIERRE RÉCUPÉRÉE", Color("#ffe18a"), 0.30)
			"dig":
				_show_event_banner("EXCAVATION", Color("#d2a16f"), 0.30)
			"cut":
				_show_event_banner("ARBRE COUPÉ", Color("#9fd978"), 0.30)
			_:
				pass

func _show_event_banner(message: String, color: Color, hold: float) -> void:
	event_banner.text = message
	event_banner.add_theme_color_override("font_color", color)
	event_banner.modulate.a = 0.0
	event_banner.scale = Vector2(0.92, 0.92)
	event_banner.pivot_offset = event_banner.size * 0.5
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(event_banner, "modulate:a", 1.0, 0.08)
	tween.parallel().tween_property(event_banner, "scale", Vector2.ONE, 0.10)
	tween.tween_interval(hold)
	tween.tween_property(event_banner, "modulate:a", 0.0, 0.20)

func _flash_screen(color: Color) -> void:
	effect_flash.color = color
	var tween := create_tween()
	var transparent := Color(color.r, color.g, color.b, 0.0)
	tween.tween_property(effect_flash, "color", transparent, 0.18)

func _pulse_control(control: Control, color: Color) -> void:
	control.pivot_offset = control.size * 0.5
	control.modulate = color
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(control, "scale", Vector2(1.12, 1.12), 0.08)
	tween.tween_property(control, "scale", Vector2.ONE, 0.12)
	tween.parallel().tween_property(control, "modulate", Color.WHITE, 0.18)

func _finish_game() -> void:
	if finishing:
		return
	finishing = true
	status_label.text = "Fin de simulation • export actions.txt..."
	audio.play_finish()
	_show_event_banner("MISSION TERMINÉE", Color("#ffe08a"), 1.0)
	var actions_text := str(simulation_data.get("actions_txt", ""))
	var actions_path := game_session.save_actions_text(actions_text)
	if actions_path.is_empty():
		status_label.text = "Erreur : impossible de sauvegarder actions.txt"
		finishing = false
		paused = true
		return
	var summary: Dictionary = BackendStateAdapter.result_to_summary(simulation_data, playback_state)
	game_session.set_result(summary, actions_path)
	await get_tree().create_timer(0.45).timeout
	get_tree().change_scene_to_file("res://scenes/menu/ResultScreen.tscn")
