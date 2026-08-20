class_name BoardEffectPulse
extends Control

var effect_color: Color = Color.WHITE
var caption: String = ""
var ring_radius: float = 18.0

func setup(color: Color, text: String, radius: float = 18.0) -> void:
	effect_color = color
	caption = text
	ring_radius = radius
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(radius * 4.0, radius * 4.0)
	size = custom_minimum_size
	pivot_offset = size * 0.5
	queue_redraw()

func play() -> void:
	modulate.a = 0.0
	scale = Vector2(0.65, 0.65)
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "modulate:a", 1.0, 0.08)
	tween.parallel().tween_property(self, "scale", Vector2(1.08, 1.08), 0.16)
	tween.tween_property(self, "modulate:a", 0.0, 0.28)
	tween.parallel().tween_property(self, "scale", Vector2(1.45, 1.45), 0.28)
	tween.finished.connect(queue_free)

func _draw() -> void:
	var center := size * 0.5
	draw_circle(center, ring_radius * 0.55, Color(effect_color.r, effect_color.g, effect_color.b, 0.14))
	draw_arc(center, ring_radius, 0.0, TAU, 36, effect_color, 3.0)
	if caption.is_empty():
		return
	var font: Font = ThemeDB.fallback_font
	var font_size: int = maxi(10, int(ring_radius * 0.70))
	var width: float = ring_radius * 3.4
	draw_string(font, center + Vector2(-width * 0.5, -ring_radius * 1.15), caption, HORIZONTAL_ALIGNMENT_CENTER, width, font_size, effect_color)
