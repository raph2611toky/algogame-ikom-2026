extends Control

const BUTTON_NORMAL = preload("res://assets/menu/ui/button_start_normal.png")
const BUTTON_HOVER = preload("res://assets/menu/ui/button_start_hover.png")
const BUTTON_PRESSED = preload("res://assets/menu/ui/button_start_pressed.png")

@onready var logo: TextureRect = $Logo
@onready var left_contact_shadow: TextureRect = $LeftContactShadow
@onready var right_contact_shadow: TextureRect = $RightContactShadow
@onready var ikotofosa_shadow: TextureRect = $IkotofosaShadow
@onready var ikotofosa: TextureRect = $Ikotofosa
@onready var imahaki_shadow: TextureRect = $ImahakiShadow
@onready var imahaki: TextureRect = $Imahaki
@onready var start_button: Button = $StartButton

func _ready() -> void:
	_setup_start_button()
	start_button.pivot_offset = start_button.size / 2.0
	start_button.pressed.connect(_on_start_button_pressed)
	start_button.mouse_entered.connect(_on_start_button_mouse_entered)
	start_button.mouse_exited.connect(_on_start_button_mouse_exited)
	_animate_intro()

func _setup_start_button() -> void:
	start_button.text = ""
	start_button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var normal_style := StyleBoxTexture.new()
	normal_style.texture = BUTTON_NORMAL
	normal_style.texture_margin_left = 8
	normal_style.texture_margin_top = 10
	normal_style.texture_margin_right = 8
	normal_style.texture_margin_bottom = 10
	start_button.add_theme_stylebox_override("normal", normal_style)

	var hover_style := StyleBoxTexture.new()
	hover_style.texture = BUTTON_HOVER
	hover_style.texture_margin_left = 8
	hover_style.texture_margin_top = 10
	hover_style.texture_margin_right = 8
	hover_style.texture_margin_bottom = 10
	start_button.add_theme_stylebox_override("hover", hover_style)

	var pressed_style := StyleBoxTexture.new()
	pressed_style.texture = BUTTON_PRESSED
	pressed_style.texture_margin_left = 8
	pressed_style.texture_margin_top = 10
	pressed_style.texture_margin_right = 8
	pressed_style.texture_margin_bottom = 10
	start_button.add_theme_stylebox_override("pressed", pressed_style)
	start_button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())

func _animate_intro() -> void:
	logo.modulate.a = 0.0
	left_contact_shadow.modulate.a = 0.0
	right_contact_shadow.modulate.a = 0.0
	ikotofosa.modulate.a = 0.0
	ikotofosa_shadow.modulate.a = 0.0
	imahaki.modulate.a = 0.0
	imahaki_shadow.modulate.a = 0.0
	start_button.modulate.a = 0.0

	logo.position.y -= 14.0
	ikotofosa.position.x -= 16.0
	ikotofosa_shadow.position.x -= 16.0
	imahaki.position.x += 18.0
	imahaki_shadow.position.x += 18.0
	start_button.position.y += 8.0

	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(logo, "modulate:a", 1.0, 0.45)
	tween.parallel().tween_property(logo, "position:y", logo.position.y + 14.0, 0.45)
	tween.parallel().tween_property(left_contact_shadow, "modulate:a", 0.62, 0.40)
	tween.parallel().tween_property(right_contact_shadow, "modulate:a", 0.84, 0.40)

	tween.tween_property(ikotofosa_shadow, "modulate:a", 0.14, 0.45)
	tween.parallel().tween_property(ikotofosa, "modulate:a", 1.0, 0.50)
	tween.parallel().tween_property(ikotofosa, "position:x", ikotofosa.position.x + 16.0, 0.50)
	tween.parallel().tween_property(ikotofosa_shadow, "position:x", ikotofosa_shadow.position.x + 16.0, 0.50)

	tween.parallel().tween_property(imahaki_shadow, "modulate:a", 0.19, 0.45)
	tween.parallel().tween_property(imahaki, "modulate:a", 1.0, 0.50)
	tween.parallel().tween_property(imahaki, "position:x", imahaki.position.x - 18.0, 0.50)
	tween.parallel().tween_property(imahaki_shadow, "position:x", imahaki_shadow.position.x - 18.0, 0.50)

	tween.tween_property(start_button, "modulate:a", 1.0, 0.30)
	tween.parallel().tween_property(start_button, "position:y", start_button.position.y - 8.0, 0.30)

func _on_start_button_mouse_entered() -> void:
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(start_button, "scale", Vector2(1.006, 1.006), 0.07)

func _on_start_button_mouse_exited() -> void:
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(start_button, "scale", Vector2.ONE, 0.07)

func _on_start_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn")
