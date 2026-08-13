extends HBoxContainer

signal speed_changed(multiplier: float)
signal pause_toggled(paused: bool)

var _paused := false

func _on_pause_pressed() -> void:
    _paused = not _paused
    pause_toggled.emit(_paused)

func _on_speed_1_pressed() -> void:
    speed_changed.emit(1.0)

func _on_speed_2_pressed() -> void:
    speed_changed.emit(2.0)

func _on_speed_4_pressed() -> void:
    speed_changed.emit(4.0)
