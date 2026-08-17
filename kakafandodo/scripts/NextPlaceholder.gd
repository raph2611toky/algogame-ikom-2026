extends Node3D

func _ready() -> void:
    var env := WorldEnvironment.new()
    var e := Environment.new()
    e.background_mode = Environment.BG_COLOR
    e.background_color = Color("1b211b")
    env.environment = e
    add_child(env)

    var camera := Camera3D.new()
    camera.position = Vector3(0, 0, 6)
    camera.current = true
    add_child(camera)

    var label := Label3D.new()
    label.text = "ÉTAPE 2 : MENU PRINCIPAL\nJOUER • MISSIONS • PARAMÈTRES • CRÉDITS • QUITTER"
    label.font_size = 46
    label.outline_size = 8
    label.position = Vector3(0, 0, 0)
    label.modulate = Color("e1b65c")
    label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    add_child(label)

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
        get_tree().change_scene_to_file("res://scenes/Main.tscn")
