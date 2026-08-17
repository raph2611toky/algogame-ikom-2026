shader_type canvas_item;

uniform float glow_strength : hint_range(0.0, 0.5) = 0.08;
uniform float vignette_strength : hint_range(0.0, 1.0) = 0.20;
uniform float pulse : hint_range(0.0, 1.0) = 0.0;

void fragment() {
    vec4 c = texture(TEXTURE, UV);
    vec2 p = UV - vec2(0.5);
    float d = length(p) * 1.42;
    float vignette = smoothstep(0.55, 1.0, d) * vignette_strength;
    c.rgb += glow_strength * (0.35 + pulse * 0.65);
    c.rgb *= 1.0 - vignette;
    COLOR = c;
}
