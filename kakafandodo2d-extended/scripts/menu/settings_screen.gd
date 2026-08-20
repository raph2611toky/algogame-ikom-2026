extends Control

const GameAudioScript = preload("res://scripts/audio/game_audio.gd")

const QUALITY_LABELS: Array[String] = ["BASSE", "MOYENNE", "ÉLEVÉE", "ULTRA"]
const LANGUAGE_LABELS: Array[String] = ["FRANÇAIS  🇫🇷", "ENGLISH  🇬🇧", "MALAGASY  🇲🇬"]
const FULLSCREEN_LABELS: Array[String] = ["NON", "OUI"]

@onready var game_session: GameSessionService = get_node("/root/GameSession") as GameSessionService

@onready var logo: TextureRect = $Logo
@onready var left_character: TextureRect = $LeftCharacter
@onready var right_character: TextureRect = $RightCharacter
@onready var panel: PanelContainer = $SettingsPanel
@onready var title_plaque: PanelContainer = $SettingsPanel/Margin/VBox/TitlePlaque
@onready var sound_row: PanelContainer = $SettingsPanel/Margin/VBox/SoundRow
@onready var music_row: PanelContainer = $SettingsPanel/Margin/VBox/MusicRow
@onready var effects_row: PanelContainer = $SettingsPanel/Margin/VBox/EffectsRow
@onready var dialogue_row: PanelContainer = $SettingsPanel/Margin/VBox/DialogueRow
@onready var quality_row: PanelContainer = $SettingsPanel/Margin/VBox/QualityRow
@onready var fullscreen_row: PanelContainer = $SettingsPanel/Margin/VBox/FullscreenRow
@onready var language_row: PanelContainer = $SettingsPanel/Margin/VBox/LanguageRow

@onready var sound_slider: HSlider = $SettingsPanel/Margin/VBox/SoundRow/HBox/Slider
@onready var sound_value: Label = $SettingsPanel/Margin/VBox/SoundRow/HBox/Value
@onready var music_slider: HSlider = $SettingsPanel/Margin/VBox/MusicRow/HBox/Slider
@onready var music_value: Label = $SettingsPanel/Margin/VBox/MusicRow/HBox/Value
@onready var effects_slider: HSlider = $SettingsPanel/Margin/VBox/EffectsRow/HBox/Slider
@onready var effects_value: Label = $SettingsPanel/Margin/VBox/EffectsRow/HBox/Value
@onready var dialogue_slider: HSlider = $SettingsPanel/Margin/VBox/DialogueRow/HBox/Slider
@onready var dialogue_value: Label = $SettingsPanel/Margin/VBox/DialogueRow/HBox/Value

@onready var quality_prev: Button = $SettingsPanel/Margin/VBox/QualityRow/HBox/Prev
@onready var quality_next: Button = $SettingsPanel/Margin/VBox/QualityRow/HBox/Next
@onready var quality_value: Label = $SettingsPanel/Margin/VBox/QualityRow/HBox/Value
@onready var fullscreen_prev: Button = $SettingsPanel/Margin/VBox/FullscreenRow/HBox/Prev
@onready var fullscreen_next: Button = $SettingsPanel/Margin/VBox/FullscreenRow/HBox/Next
@onready var fullscreen_value: Label = $SettingsPanel/Margin/VBox/FullscreenRow/HBox/Value
@onready var language_prev: Button = $SettingsPanel/Margin/VBox/LanguageRow/HBox/Prev
@onready var language_next: Button = $SettingsPanel/Margin/VBox/LanguageRow/HBox/Next
@onready var language_value: Label = $SettingsPanel/Margin/VBox/LanguageRow/HBox/Value

@onready var back_button: Button = $SettingsPanel/Margin/VBox/Buttons/BackButton
@onready var default_button: Button = $SettingsPanel/Margin/VBox/Buttons/DefaultButton
@onready var save_button: Button = $SettingsPanel/Margin/VBox/Buttons/SaveButton
@onready var top_quit_button: Button = $TopQuitButton
@onready var save_status: Label = $SettingsPanel/Margin/VBox/SaveStatus

var strategy_row: PanelContainer
var strategy_option: OptionButton
var backend_row: PanelContainer
var backend_host_input: LineEdit
var backend_port_input: SpinBox
var backend_test_button: Button
var backend_status_label: Label
var _strategy_names: Array[String] = []
var _loading_values: bool = false

var _audio: GameAudio
var _saved_settings: Dictionary = {}

func _ready() -> void:
	_audio = GameAudioScript.new()
	add_child(_audio)
	_build_dynamic_backend_rows()
	_style_screen()
	game_session.settings_changed.connect(_load_values)
	await game_session.refresh_settings_from_backend()
	await _load_strategy_catalog()
	_saved_settings = game_session.settings.duplicate(true)
	_load_values()
	_bind_slider(sound_slider, sound_value, "sound")
	_bind_slider(music_slider, music_value, "music")
	_bind_slider(effects_slider, effects_value, "effects")
	_bind_slider(dialogue_slider, dialogue_value, "dialogue")

	quality_prev.pressed.connect(func(): _cycle_quality(-1))
	quality_next.pressed.connect(func(): _cycle_quality(1))
	fullscreen_prev.pressed.connect(func(): _cycle_fullscreen())
	fullscreen_next.pressed.connect(func(): _cycle_fullscreen())
	language_prev.pressed.connect(func(): _cycle_language(-1))
	language_next.pressed.connect(func(): _cycle_language(1))
	back_button.pressed.connect(_on_back)
	default_button.pressed.connect(_on_default)
	save_button.pressed.connect(_on_save)
	top_quit_button.pressed.connect(_on_quit)
	strategy_option.item_selected.connect(_on_strategy_selected)
	backend_host_input.text_changed.connect(_on_backend_host_changed)
	backend_port_input.value_changed.connect(_on_backend_port_changed)
	backend_test_button.pressed.connect(_on_test_backend)
	_animate_intro()

func _build_dynamic_backend_rows() -> void:
	var vbox: VBoxContainer = $SettingsPanel/Margin/VBox
	var buttons: HBoxContainer = $SettingsPanel/Margin/VBox/Buttons

	strategy_row = PanelContainer.new()
	strategy_row.name = "StrategyRow"
	strategy_row.custom_minimum_size = Vector2(0, 58)
	var strategy_box := HBoxContainer.new()
	strategy_box.add_theme_constant_override("separation", 16)
	strategy_row.add_child(strategy_box)
	var strategy_name := Label.new()
	strategy_name.custom_minimum_size = Vector2(230, 0)
	strategy_name.text = "STRATÉGIE IA"
	strategy_name.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	strategy_name.add_theme_font_size_override("font_size", 20)
	strategy_box.add_child(strategy_name)
	strategy_option = OptionButton.new()
	strategy_option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	strategy_option.custom_minimum_size = Vector2(360, 46)
	strategy_box.add_child(strategy_option)
	vbox.add_child(strategy_row)
	vbox.move_child(strategy_row, buttons.get_index())

	backend_row = PanelContainer.new()
	backend_row.name = "BackendRow"
	backend_row.custom_minimum_size = Vector2(0, 62)
	var backend_box := HBoxContainer.new()
	backend_box.add_theme_constant_override("separation", 12)
	backend_row.add_child(backend_box)
	var backend_name := Label.new()
	backend_name.custom_minimum_size = Vector2(150, 0)
	backend_name.text = "BACKEND"
	backend_name.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	backend_name.add_theme_font_size_override("font_size", 20)
	backend_box.add_child(backend_name)
	backend_host_input = LineEdit.new()
	backend_host_input.placeholder_text = "127.0.0.1"
	backend_host_input.custom_minimum_size = Vector2(230, 44)
	backend_host_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	backend_box.add_child(backend_host_input)
	backend_port_input = SpinBox.new()
	backend_port_input.min_value = 1
	backend_port_input.max_value = 65535
	backend_port_input.step = 1
	backend_port_input.custom_minimum_size = Vector2(120, 44)
	backend_box.add_child(backend_port_input)
	backend_test_button = Button.new()
	backend_test_button.text = "TESTER"
	backend_test_button.custom_minimum_size = Vector2(120, 44)
	backend_box.add_child(backend_test_button)
	backend_status_label = Label.new()
	backend_status_label.custom_minimum_size = Vector2(135, 0)
	backend_status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	backend_status_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	backend_status_label.add_theme_font_size_override("font_size", 15)
	backend_box.add_child(backend_status_label)
	vbox.add_child(backend_row)
	vbox.move_child(backend_row, buttons.get_index())

func _load_strategy_catalog() -> void:
	_strategy_names.clear()
	strategy_option.clear()
	var loaded := await game_session.refresh_strategy_catalog()
	if loaded:
		for item in game_session.available_strategies:
			var name := str(item.get("name", ""))
			if name.is_empty():
				continue
			_strategy_names.append(name)
			var label := str(item.get("label", name))
			if bool(item.get("recommended", false)):
				label += "  ★"
			strategy_option.add_item(label)
	else:
		var current := str(game_session.get_strategy_options().get("name", "portfolio_v14"))
		_strategy_names.append(current)
		strategy_option.add_item(current)
	_update_strategy_selection()

func _update_strategy_selection() -> void:
	if strategy_option == null or _strategy_names.is_empty():
		return
	var current := str(game_session.get_strategy_options().get("name", game_session.default_strategy_name))
	var index := _strategy_names.find(current)
	if index < 0:
		_strategy_names.append(current)
		strategy_option.add_item(current)
		index = _strategy_names.size() - 1
	strategy_option.select(index)

func _on_strategy_selected(index: int) -> void:
	if _loading_values or index < 0 or index >= _strategy_names.size():
		return
	var options := game_session.get_strategy_options()
	options["name"] = _strategy_names[index]
	game_session.settings["strategy"] = options
	_mark_dirty()

func _on_backend_host_changed(value: String) -> void:
	if _loading_values or BackendAPI.endpoint_forced:
		return
	game_session.settings["backend_host"] = value.strip_edges()
	_mark_dirty()

func _on_backend_port_changed(value: float) -> void:
	if _loading_values or BackendAPI.endpoint_forced:
		return
	game_session.settings["backend_port"] = int(value)
	_mark_dirty()

func _on_test_backend() -> void:
	_audio.play_ui_click()

	# En développement, on teste la valeur saisie.
	# En build packagé, l'endpoint est imposé par le launcher et reste inchangé.
	if not BackendAPI.endpoint_forced:
		game_session.settings["backend_host"] = backend_host_input.text.strip_edges()
		game_session.settings["backend_port"] = int(backend_port_input.value)
		game_session.apply_backend_endpoint()

	backend_test_button.disabled = true
	backend_status_label.text = "TEST..."
	var response: Dictionary = await BackendAPI.health()
	backend_test_button.disabled = false

	if bool(response.get("ok", false)):
		backend_status_label.text = "EMBARQUÉ • CONNECTÉ" if BackendAPI.endpoint_forced else "CONNECTÉ"
		backend_status_label.add_theme_color_override("font_color", Color("#9fe28f"))
		await _load_strategy_catalog()
	else:
		backend_status_label.text = "EMBARQUÉ • INDISPONIBLE" if BackendAPI.endpoint_forced else "INDISPONIBLE"
		backend_status_label.add_theme_color_override("font_color", Color("#f06b5f"))

	if not BackendAPI.endpoint_forced:
		_mark_dirty()

func _style_screen() -> void:
	UIStyle.apply_panel(panel)
	panel.add_theme_stylebox_override("panel", _panel_style())
	title_plaque.add_theme_stylebox_override("panel", _plaque_style())
	for row_value in [sound_row, music_row, effects_row, dialogue_row, quality_row, fullscreen_row, language_row, strategy_row, backend_row]:
		var row: PanelContainer = row_value
		row.add_theme_stylebox_override("panel", _row_style())
	for slider_value in [sound_slider, music_slider, effects_slider, dialogue_slider]:
		var slider: HSlider = slider_value
		_style_slider(slider)
	for button_value in [quality_prev, quality_next, fullscreen_prev, fullscreen_next, language_prev, language_next]:
		var nav_button: Button = button_value
		_apply_nav_button(nav_button)
	for action_button_value in [back_button, default_button, save_button]:
		var action_button: Button = action_button_value
		UIStyle.apply_button(action_button, 22)
	_apply_quit_button(top_quit_button)
	UIStyle.apply_button(backend_test_button, 17)
	strategy_option.add_theme_font_size_override("font_size", 18)
	backend_host_input.add_theme_font_size_override("font_size", 18)
	backend_port_input.add_theme_font_size_override("font_size", 18)

func _apply_quit_button(button: Button) -> void:
	var normal := StyleBoxFlat.new()
	normal.bg_color = Color(0.20, 0.08, 0.06, 0.90)
	normal.border_color = Color("#8e3b31")
	normal.set_border_width_all(2)
	normal.corner_radius_top_left = 9
	normal.corner_radius_top_right = 9
	normal.corner_radius_bottom_left = 9
	normal.corner_radius_bottom_right = 9
	var hover: StyleBoxFlat = normal.duplicate()
	hover.bg_color = Color("#c7362f")
	hover.border_color = Color("#f06b5f")
	var pressed: StyleBoxFlat = hover.duplicate()
	pressed.bg_color = Color("#972720")
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	button.add_theme_color_override("font_color", Color("#f4d8c5"))
	button.add_theme_color_override("font_hover_color", Color.WHITE)
	button.add_theme_color_override("font_pressed_color", Color.WHITE)
	button.add_theme_font_size_override("font_size", 20)
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

func _style_slider(slider: HSlider) -> void:
	var track: StyleBoxFlat = StyleBoxFlat.new()
	track.bg_color = Color("#3f2a1b")
	track.corner_radius_top_left = 6
	track.corner_radius_top_right = 6
	track.corner_radius_bottom_left = 6
	track.corner_radius_bottom_right = 6
	track.content_margin_left = 0
	track.content_margin_right = 0
	track.content_margin_top = 4
	track.content_margin_bottom = 4
	var grabber: StyleBoxFlat = StyleBoxFlat.new()
	grabber.bg_color = Color("#ae8452")
	grabber.border_color = Color("#5c3a21")
	grabber.set_border_width_all(2)
	grabber.corner_radius_top_left = 6
	grabber.corner_radius_top_right = 6
	grabber.corner_radius_bottom_left = 6
	grabber.corner_radius_bottom_right = 6
	slider.add_theme_stylebox_override("slider", track)
	slider.add_theme_stylebox_override("grabber_area", track)
	slider.add_theme_stylebox_override("grabber_area_highlight", track)
	slider.add_theme_stylebox_override("grabber", grabber)
	slider.add_theme_stylebox_override("grabber_highlight", grabber)
	slider.add_theme_constant_override("grabber_offset", 2)
	slider.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

func _apply_nav_button(button: Button) -> void:
	var normal: StyleBoxFlat = StyleBoxFlat.new()
	normal.bg_color = Color("#755033")
	normal.border_color = Color("#4a2f1b")
	normal.set_border_width_all(2)
	normal.corner_radius_top_left = 8
	normal.corner_radius_top_right = 8
	normal.corner_radius_bottom_left = 8
	normal.corner_radius_bottom_right = 8
	normal.content_margin_left = 10
	normal.content_margin_right = 10
	normal.content_margin_top = 6
	normal.content_margin_bottom = 6
	var hover: StyleBoxFlat = normal.duplicate()
	hover.bg_color = Color("#8a603d")
	var pressed: StyleBoxFlat = normal.duplicate()
	pressed.bg_color = Color("#634128")
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	button.add_theme_font_size_override("font_size", 18)
	button.add_theme_color_override("font_color", Color("#f6e1bd"))
	button.add_theme_color_override("font_outline_color", Color("#3e2314"))
	button.add_theme_constant_override("outline_size", 3)
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

func _panel_style() -> StyleBoxFlat:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.34, 0.24, 0.15, 0.95)
	style.border_color = Color("#8f6b48")
	style.set_border_width_all(5)
	style.corner_radius_top_left = 18
	style.corner_radius_top_right = 18
	style.corner_radius_bottom_left = 18
	style.corner_radius_bottom_right = 18
	style.shadow_color = Color(0, 0, 0, 0.42)
	style.shadow_size = 14
	return style

func _plaque_style() -> StyleBoxFlat:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color("#82603f")
	style.border_color = Color("#5b3a22")
	style.set_border_width_all(4)
	style.corner_radius_top_left = 12
	style.corner_radius_top_right = 12
	style.corner_radius_bottom_left = 12
	style.corner_radius_bottom_right = 12
	style.content_margin_left = 18
	style.content_margin_right = 18
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	return style

func _row_style() -> StyleBoxFlat:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color("#5d4029")
	style.border_color = Color("#7d5b3e")
	style.set_border_width_all(2)
	style.corner_radius_top_left = 10
	style.corner_radius_top_right = 10
	style.corner_radius_bottom_left = 10
	style.corner_radius_bottom_right = 10
	return style

func _bind_slider(slider: HSlider, label: Label, key: String) -> void:
	slider.value_changed.connect(func(value: float) -> void:
		game_session.settings[key] = int(value)
		label.text = "%d%%" % int(value)
		game_session.apply_settings()
		_mark_dirty()
	)

func _load_values() -> void:
	_loading_values = true
	sound_slider.value = int(game_session.settings["sound"])
	music_slider.value = int(game_session.settings["music"])
	effects_slider.value = int(game_session.settings["effects"])
	dialogue_slider.value = int(game_session.settings["dialogue"])
	sound_value.text = "%d%%" % int(sound_slider.value)
	music_value.text = "%d%%" % int(music_slider.value)
	effects_value.text = "%d%%" % int(effects_slider.value)
	dialogue_value.text = "%d%%" % int(dialogue_slider.value)
	quality_value.text = QUALITY_LABELS[clampi(int(game_session.settings["quality"]), 0, QUALITY_LABELS.size() - 1)]
	fullscreen_value.text = FULLSCREEN_LABELS[1 if bool(game_session.settings["fullscreen"]) else 0]
	language_value.text = LANGUAGE_LABELS[clampi(int(game_session.settings["language"]), 0, LANGUAGE_LABELS.size() - 1)]

	if BackendAPI.endpoint_forced:
		backend_host_input.text = BackendAPI.backend_host
		backend_port_input.value = BackendAPI.backend_port
		backend_status_label.text = "EMBARQUÉ • CONNECTÉ" if game_session.backend_online else "EMBARQUÉ"
	else:
		backend_host_input.text = str(game_session.settings.get("backend_host", "127.0.0.1"))
		backend_port_input.value = int(game_session.settings.get("backend_port", 8000))
		backend_status_label.text = "CONNECTÉ" if game_session.backend_online else "LOCAL"

	backend_host_input.editable = not BackendAPI.endpoint_forced
	backend_port_input.editable = not BackendAPI.endpoint_forced
	backend_test_button.text = "VÉRIFIER" if BackendAPI.endpoint_forced else "TESTER"

	_update_strategy_selection()
	_loading_values = false

func _cycle_quality(delta: int) -> void:
	_audio.play_ui_click()
	var next_index: int = wrapi(int(game_session.settings["quality"]) + delta, 0, QUALITY_LABELS.size())
	game_session.settings["quality"] = next_index
	game_session.apply_settings()
	_mark_dirty()
	_load_values()

func _cycle_fullscreen() -> void:
	_audio.play_ui_click()
	game_session.settings["fullscreen"] = not bool(game_session.settings["fullscreen"])
	game_session.apply_settings()
	_mark_dirty()
	_load_values()

func _cycle_language(delta: int) -> void:
	_audio.play_ui_click()
	var next_index: int = wrapi(int(game_session.settings["language"]) + delta, 0, LANGUAGE_LABELS.size())
	game_session.settings["language"] = next_index
	game_session.apply_settings()
	_mark_dirty()
	_load_values()

func _animate_intro() -> void:
	logo.modulate.a = 0.0
	left_character.modulate.a = 0.0
	right_character.modulate.a = 0.0
	panel.modulate.a = 0.0
	logo.position.y -= 12.0
	left_character.position.x -= 18.0
	right_character.position.x += 18.0
	panel.position.y += 12.0
	var tween: Tween = create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(logo, "modulate:a", 1.0, 0.35)
	tween.parallel().tween_property(logo, "position:y", logo.position.y + 12.0, 0.35)
	tween.parallel().tween_property(left_character, "modulate:a", 1.0, 0.42)
	tween.parallel().tween_property(left_character, "position:x", left_character.position.x + 18.0, 0.42)
	tween.parallel().tween_property(right_character, "modulate:a", 1.0, 0.42)
	tween.parallel().tween_property(right_character, "position:x", right_character.position.x - 18.0, 0.42)
	tween.tween_property(panel, "modulate:a", 1.0, 0.32)
	tween.parallel().tween_property(panel, "position:y", panel.position.y - 12.0, 0.32)

func _mark_dirty() -> void:
	save_status.text = "MODIFICATIONS NON ENREGISTRÉES"
	save_status.add_theme_color_override("font_color", Color("#f1c875"))

func _on_default() -> void:
	_audio.play_ui_click()
	game_session.preview_default_settings()
	_mark_dirty()
	_load_values()

func _on_save() -> void:
	_audio.play_ui_click()
	save_button.disabled = true
	save_button.text = "ENREGISTREMENT..."
	var response: Dictionary = await game_session.persist_settings_now()
	save_button.disabled = false
	save_button.text = "ENREGISTRER"
	_saved_settings = game_session.settings.duplicate(true)
	if bool(response.get("ok", false)):
		save_status.text = "PARAMÈTRES ENREGISTRÉS"
		save_status.add_theme_color_override("font_color", Color("#9fe28f"))
	else:
		save_status.text = "ENREGISTRÉ EN LOCAL • BACKEND INDISPONIBLE"
		save_status.add_theme_color_override("font_color", Color("#f1c875"))

func _on_back() -> void:
	_audio.play_ui_click()
	if not _saved_settings.is_empty():
		game_session.replace_settings(_saved_settings, true)
	get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn")

func _on_quit() -> void:
	_audio.play_ui_click()
	get_tree().quit()
