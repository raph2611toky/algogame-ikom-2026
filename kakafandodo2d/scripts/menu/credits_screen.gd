extends Control

@onready var panel: PanelContainer = $Panel
@onready var back_button: Button = $Panel/Margin/VBox/BackButton

func _ready() -> void:
	UIStyle.apply_panel(panel)
	UIStyle.apply_button(back_button, 22)
	back_button.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/menu/MainMenu.tscn"))
