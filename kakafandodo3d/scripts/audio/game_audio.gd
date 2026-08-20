class_name GameAudio
extends Node

const MOVE_SOUND: AudioStream = preload("res://assets/audio/liv4/move.wav")
const HOP_SOUND: AudioStream = preload("res://assets/audio/liv4/hop.wav")
const CLIMB_SOUND: AudioStream = preload("res://assets/audio/liv4/climb.wav")
const PUSH_SOUND: AudioStream = preload("res://assets/audio/liv4/push.wav")
const COLLECT_SOUND: AudioStream = preload("res://assets/audio/liv4/collect.wav")
const HACK_SOUND: AudioStream = preload("res://assets/audio/liv4/hack.wav")
const DIG_SOUND: AudioStream = preload("res://assets/audio/liv4/dig.wav")
const CUT_SOUND: AudioStream = preload("res://assets/audio/liv4/cut.wav")
const FILL_SOUND: AudioStream = preload("res://assets/audio/liv4/fill.wav")
const CHEST_HIDDEN_SOUND: AudioStream = preload("res://assets/audio/liv4/chest_hidden.wav")
const CHEST_LOST_SOUND: AudioStream = preload("res://assets/audio/liv4/chest_lost.wav")
const ROTATE_SOUND: AudioStream = preload("res://assets/audio/liv4/rotate.wav")
const UI_CLICK_SOUND: AudioStream = preload("res://assets/audio/liv4/ui_click.wav")
const MISSION_START_SOUND: AudioStream = preload("res://assets/audio/liv4/mission_start.wav")
const FINISH_SOUND: AudioStream = preload("res://assets/audio/liv4/finish.wav")

var _last_move_ms: int = -1000

func play_ui_click() -> void:
	_play(UI_CLICK_SOUND, 1.0, -5.0)

func play_mission_start() -> void:
	_play(MISSION_START_SOUND, 1.0, -2.0)

func play_finish() -> void:
	_play(FINISH_SOUND, 1.0, -1.0)

func play_events(events: Array) -> void:
	var strong_sound_played := false
	for event_value in events:
		var event_data: Dictionary = event_value
		var event_type: String = str(event_data.get("type", ""))
		match event_type:
			"hack":
				_play(HACK_SOUND, 1.0, -2.0)
				strong_sound_played = true
			"dig":
				_play(DIG_SOUND, 0.94, -2.0)
				strong_sound_played = true
			"cut":
				_play(CUT_SOUND, 1.0, -2.0)
				strong_sound_played = true
			"fill":
				_play(FILL_SOUND, 1.0, -3.0)
				strong_sound_played = true
			"chest_hidden":
				_play(CHEST_HIDDEN_SOUND, 1.0, -1.0)
				strong_sound_played = true
			"chest_lost":
				_play(CHEST_LOST_SOUND, 0.92, -1.0)
				strong_sound_played = true
			"stone_pickup", "stone_steal", "stone_pickup_machine":
				_play(COLLECT_SOUND, randf_range(0.96, 1.08), -4.0)
			"rotate":
				if not strong_sound_played:
					_play(ROTATE_SOUND, randf_range(0.96, 1.04), -7.0)
			"chest_move":
				if not strong_sound_played:
					_play(PUSH_SOUND, randf_range(0.96, 1.03), -5.0)
			"move":
				_play_move_style(str(event_data.get("style", "move")))
			_:
				pass

func _play_move_style(style: String) -> void:
	var now_ms: int = Time.get_ticks_msec()
	if style == "hop":
		_play(HOP_SOUND, 1.0, -5.0)
		return
	if style == "climb":
		_play(CLIMB_SOUND, 1.0, -5.0)
		return
	if style == "push":
		_play(PUSH_SOUND, 1.0, -5.0)
		return
	if now_ms - _last_move_ms < 55:
		return
	_last_move_ms = now_ms
	_play(MOVE_SOUND, randf_range(0.95, 1.08), -10.0)

func _play(stream: AudioStream, pitch: float = 1.0, volume_db: float = 0.0) -> void:
	if not _audio_available():
		return
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = "Effects"
	player.pitch_scale = pitch
	player.volume_db = volume_db
	add_child(player)
	player.finished.connect(player.queue_free)
	player.play()

func _audio_available() -> bool:
	var driver := AudioServer.get_driver_name()
	if driver.is_empty() or driver.to_lower() == "dummy":
		return false
	return not AudioServer.get_output_device_list().is_empty()
