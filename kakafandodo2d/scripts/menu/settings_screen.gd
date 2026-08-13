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

var _audio: GameAudio
var _saved_settings: Dictionary = {}

func _ready() -> void:
	_audio = GameAudioScript.new()
	add_child(_audio)
	_style_screen()
	game_session.settings_changed.connect(_load_values)
	await game_session.refresh_settings_from_backend()
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
	_animate_intro()

func _style_screen() -> void:
	UIStyle.apply_panel(panel)
	panel.add_theme_stylebox_override("panel", _panel_style())
	title_plaque.add_theme_stylebox_override("panel", _plaque_style())
	for row_value in [sound_row, music_row, effects_row, dialogue_row, quality_row, fullscreen_row, language_row]:
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
