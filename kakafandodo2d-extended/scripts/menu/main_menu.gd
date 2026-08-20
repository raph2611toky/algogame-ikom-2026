extends Control

const BUTTON_NORMAL = preload("res://assets/menu/ui/menu_button_normal.svg")
const BUTTON_HOVER = preload("res://assets/menu/ui/menu_button_hover.svg")
const BUTTON_PRESSED = preload("res://assets/menu/ui/menu_button_pressed.svg")
const GameAudioScript = preload("res://scripts/audio/game_audio.gd")

@onready var logo: TextureRect = $Logo
@onready var ikotofosa: TextureRect = $Ikotofosa
@onready var ikotofosa_shadow: TextureRect = $IkotofosaShadow
@onready var imahaki: TextureRect = $Imahaki
@onready var imahaki_shadow: TextureRect = $ImahakiShadow
@onready var left_contact_shadow: TextureRect = $LeftContactShadow
@onready var right_contact_shadow: TextureRect = $RightContactShadow
@onready var crystal_deco: TextureRect = $CrystalDeco
@onready var chest_deco: TextureRect = $ChestDeco
@onready var play_button: Button = $CenterButtons/PlayButton
@onready var missions_button: Button = $CenterButtons/BottomButtons/MissionsButton
@onready var settings_button: Button = $CenterButtons/BottomButtons/SettingsButton
@onready var credits_button: Button = $CenterButtons/BottomButtons/CreditsButton
@onready var quit_button: Button = $CenterButtons/BottomButtons/QuitButton
@onready var center_buttons: VBoxContainer = $CenterButtons

var _audio: GameAudio

func _ready() -> void:
	_audio = GameAudioScript.new()
	add_child(_audio)
	_setup_button(play_button, 54)
	_setup_button(missions_button, 23)
	_setup_button(settings_button, 23)
	_setup_button(credits_button, 23)
	_setup_button(quit_button, 23)

	play_button.pressed.connect(_on_play_pressed)
	missions_button.pressed.connect(_on_missions_pressed)
	settings_button.pressed.connect(_on_settings_pressed)
	credits_button.pressed.connect(_on_credits_pressed)
	quit_button.pressed.connect(_on_quit_pressed)

	for button_value in [play_button, missions_button, settings_button, credits_button, quit_button]:
		var button: Button = button_value
		button.mouse_entered.connect(_animate_button_hover.bind(button, true))
		button.mouse_exited.connect(_animate_button_hover.bind(button, false))
		button.pivot_offset = button.size / 2.0

	_animate_intro()

func _setup_button(button: Button, font_size: int) -> void:
	button.add_theme_font_size_override("font_size", font_size)
	button.add_theme_color_override("font_color", Color("#3a2411"))
	button.add_theme_color_override("font_hover_color", Color("#28170b"))
	button.add_theme_color_override("font_pressed_color", Color("#4a2d16"))
	button.add_theme_color_override("font_outline_color", Color("#efc87a"))
	button.add_theme_constant_override("outline_size", 2)
	button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	button.alignment = HORIZONTAL_ALIGNMENT_CENTER

	var normal_style: StyleBoxTexture = StyleBoxTexture.new()
	normal_style.texture = BUTTON_NORMAL
	normal_style.texture_margin_left = 50
	normal_style.texture_margin_top = 44
	normal_style.texture_margin_right = 50
	normal_style.texture_margin_bottom = 44
	button.add_theme_stylebox_override("normal", normal_style)

	var hover_style: StyleBoxTexture = StyleBoxTexture.new()
	hover_style.texture = BUTTON_HOVER
	hover_style.texture_margin_left = 50
	hover_style.texture_margin_top = 44
	hover_style.texture_margin_right = 50
	hover_style.texture_margin_bottom = 44
	button.add_theme_stylebox_override("hover", hover_style)

	var pressed_style: StyleBoxTexture = StyleBoxTexture.new()
	pressed_style.texture = BUTTON_PRESSED
	pressed_style.texture_margin_left = 50
	pressed_style.texture_margin_top = 44
	pressed_style.texture_margin_right = 50
	pressed_style.texture_margin_bottom = 44
	button.add_theme_stylebox_override("pressed", pressed_style)

func _animate_intro() -> void:
	logo.modulate.a = 0.0
	ikotofosa.modulate.a = 0.0
	ikotofosa_shadow.modulate.a = 0.0
	imahaki.modulate.a = 0.0
	imahaki_shadow.modulate.a = 0.0
	left_contact_shadow.modulate.a = 0.0
	right_contact_shadow.modulate.a = 0.0
	crystal_deco.modulate.a = 0.0
	chest_deco.modulate.a = 0.0
	center_buttons.modulate.a = 0.0

	logo.position.y -= 22.0
	ikotofosa.position.x -= 18.0
	ikotofosa_shadow.position.x -= 18.0
	imahaki.position.x += 18.0
	imahaki_shadow.position.x += 18.0
	center_buttons.position.y += 14.0
	crystal_deco.scale = Vector2(0.5, 0.5)

	var tween: Tween = create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(logo, "modulate:a", 1.0, 0.42)
	tween.parallel().tween_property(logo, "position:y", logo.position.y + 22.0, 0.42)
	tween.parallel().tween_property(left_contact_shadow, "modulate:a", 0.62, 0.45)
	tween.parallel().tween_property(right_contact_shadow, "modulate:a", 0.82, 0.45)
	tween.parallel().tween_property(crystal_deco, "modulate:a", 1.0, 0.45)
	tween.parallel().tween_property(crystal_deco, "scale", Vector2.ONE, 0.45)
	tween.parallel().tween_property(chest_deco, "modulate:a", 1.0, 0.45)
	tween.tween_property(ikotofosa_shadow, "modulate:a", 0.15, 0.45)
	tween.parallel().tween_property(ikotofosa, "modulate:a", 1.0, 0.50)
	tween.parallel().tween_property(ikotofosa, "position:x", ikotofosa.position.x + 18.0, 0.50)
	tween.parallel().tween_property(ikotofosa_shadow, "position:x", ikotofosa_shadow.position.x + 18.0, 0.50)
	tween.parallel().tween_property(imahaki_shadow, "modulate:a", 0.18, 0.45)
	tween.parallel().tween_property(imahaki, "modulate:a", 1.0, 0.50)
	tween.parallel().tween_property(imahaki, "position:x", imahaki.position.x - 18.0, 0.50)
	tween.parallel().tween_property(imahaki_shadow, "position:x", imahaki_shadow.position.x - 18.0, 0.50)
	tween.tween_property(center_buttons, "modulate:a", 1.0, 0.32)
	tween.parallel().tween_property(center_buttons, "position:y", center_buttons.position.y - 14.0, 0.32)

func _animate_button_hover(button: Button, entering: bool) -> void:
	var tween: Tween = create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(button, "scale", Vector2(1.02, 1.02) if entering else Vector2.ONE, 0.08)

func _go_to(scene_path: String) -> void:
	_audio.play_ui_click()
	get_tree().change_scene_to_file(scene_path)

func _on_play_pressed() -> void:
	_go_to("res://scenes/menu/MissionSelect.tscn")

func _on_missions_pressed() -> void:
	_go_to("res://scenes/menu/MissionSelect.tscn")

func _on_settings_pressed() -> void:
	_go_to("res://scenes/menu/SettingsScreen.tscn")

func _on_credits_pressed() -> void:
	_go_to("res://scenes/menu/CreditsScreen.tscn")

func _on_quit_pressed() -> void:
	_audio.play_ui_click()
	get_tree().quit()
