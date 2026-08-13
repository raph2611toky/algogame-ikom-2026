class_name UIStyle
extends RefCounted

static func panel_style(alpha: float = 0.94) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.22, 0.14, 0.085, alpha)
	style.border_color = Color("#8a6037")
	style.set_border_width_all(4)
	style.corner_radius_top_left = 14
	style.corner_radius_top_right = 14
	style.corner_radius_bottom_left = 14
	style.corner_radius_bottom_right = 14
	style.shadow_color = Color(0, 0, 0, 0.35)
	style.shadow_size = 10
	return style

static func row_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color("#5b3c25")
	style.border_color = Color("#7c5736")
	style.set_border_width_all(2)
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	return style

static func button_style(bg: Color = Color("#82532f"), hover: Color = Color("#99643a"), pressed: Color = Color("#684020")) -> Dictionary:
	return {
		"normal": _flat(bg),
		"hover": _flat(hover),
		"pressed": _flat(pressed),
		"focus": StyleBoxEmpty.new(),
	}

static func apply_button(button: BaseButton, font_size: int = 26) -> void:
	var styles := button_style()
	button.add_theme_stylebox_override("normal", styles["normal"])
	button.add_theme_stylebox_override("hover", styles["hover"])
	button.add_theme_stylebox_override("pressed", styles["pressed"])
	button.add_theme_stylebox_override("focus", styles["focus"])
	button.add_theme_font_size_override("font_size", font_size)
	button.add_theme_color_override("font_color", Color("#f2dfbd"))
	button.add_theme_color_override("font_hover_color", Color("#fff1d0"))
	button.add_theme_color_override("font_pressed_color", Color("#dcc099"))
	button.add_theme_color_override("font_outline_color", Color("#3e2314"))
	button.add_theme_constant_override("outline_size", 4)
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

static func apply_panel(panel: PanelContainer) -> void:
	panel.add_theme_stylebox_override("panel", panel_style())

static func apply_progress(bar: ProgressBar, fill_color: Color) -> void:
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color("#2d2017")
	bg.corner_radius_top_left = 6
	bg.corner_radius_top_right = 6
	bg.corner_radius_bottom_left = 6
	bg.corner_radius_bottom_right = 6
	var fill := StyleBoxFlat.new()
	fill.bg_color = fill_color
	fill.corner_radius_top_left = 6
	fill.corner_radius_top_right = 6
	fill.corner_radius_bottom_left = 6
	fill.corner_radius_bottom_right = 6
	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)
	bar.add_theme_color_override("font_color", Color.WHITE)
	bar.add_theme_font_size_override("font_size", 16)

static func _flat(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = Color("#3a2416")
	style.set_border_width_all(3)
	style.corner_radius_top_left = 9
	style.corner_radius_top_right = 9
	style.corner_radius_bottom_left = 9
	style.corner_radius_bottom_right = 9
	style.content_margin_left = 16
	style.content_margin_right = 16
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	return style
