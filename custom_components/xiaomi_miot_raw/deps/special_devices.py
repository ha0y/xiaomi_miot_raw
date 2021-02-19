SPECIAL_DEVICES={
    "chuangmi.plug.212a01":{
        "device_type": ['switch','sensor'],
        "mapping": {"switch": {"switch_status": {"siid": 2, "piid": 1}, "temperature": {"siid": 2, "piid": 6}, "working_time": {"siid": 2, "piid": 7}}, "power_consumption": {"power_consumption": {"siid": 5, "piid": 1}, "electric_current": {"siid": 5, "piid": 2}, "voltage": {"siid": 5, "piid": 3}, "electric_power": {"siid": 5, "piid": 6}}},
        "params": {"switch": {"switch_status": {"power_on": True, "power_off": False}, "main": True}, "power_consumption": {"electric_power":{"value_ratio": 0.01, "unit": "W"}}}
    },
    "xiaomi.wifispeaker.x08c": {
        "device_type": ['media_player'],
        "mapping":{"speaker": {"volume": {"siid": 4, "piid": 1}, "mute": {"siid": 4, "piid": 2}, "playing_state": {"siid": 2, "piid": 1},"mp_sound_mode":{"siid":3,"aiid":1}}, "a_l": {"play_control_pause": {"siid": 2, "aiid": 1}, "play_control_play": {"siid": 2, "aiid": 2}, "play_control_next": {"siid": 2, "aiid": 3}, "play_control_previous": {"siid": 2, "aiid": 4}, "intelligent_speaker_play_text": {"siid": 3, "aiid": 1}, "intelligent_speaker_wake_up": {"siid": 3, "aiid": 2}, "intelligent_speaker_play_radio": {"siid": 3, "aiid": 3}, "intelligent_speaker_play_music": {"siid": 3, "aiid": 4}, "intelligent_speaker_execute_text_directive": {"siid": 3, "aiid": 5}}},
        "params": {"speaker": {"volume": {"value_range": [5, 100, 5]}, "main": True, "mp_source":{"\u64ad\u653e\u79c1\u4eba\u7535\u53f0":{"siid":3,"aiid":3},"\u64ad\u653e\u97f3\u4e50":{"siid":3,"aiid":4},"\u505c\u6b62\u95f9\u949f":{"siid":6,"aiid":1}},"mp_sound_mode":{"\u4f60\u597d":0},"playing_state": {"pause": 0, "playing": 1}}}
    },
    "syniot.curtain.syc1": {
        "device_type": ['cover'],
        "mapping":{"curtain":{"motor_control":{"siid":2,"piid":1},"target_position":{"siid":2,"piid":2},"current_position":{"siid":2,"piid":2},"motor_reverse":{"siid":2,"piid":3}},"a_l":{"curtain_motor_calibrate":{"siid":2,"aiid":1}}},
        "params": {"curtain":{"motor_control":{"stop":2,"open":0,"close":1},"target_position":{"value_range":[0,100,1]},"main":True}}
    },
}