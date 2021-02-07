SPECIAL_DEVICES={
    "chuangmi.plug.212a01":{
        "device_type": ['switch','sensor'],
        "mapping": {"switch": {"switch_status": {"siid": 2, "piid": 1}, "temperature": {"siid": 2, "piid": 6}, "working_time": {"siid": 2, "piid": 7}}, "power_consumption": {"power_consumption": {"siid": 5, "piid": 1}, "electric_current": {"siid": 5, "piid": 2}, "voltage": {"siid": 5, "piid": 3}, "electric_power": {"siid": 5, "piid": 6}}},
        "params": {"switch": {"switch_status": {"power_on": True, "power_off": False}, "main": True}, "power_consumption": {"electric_power":{"value_ratio": 0.01, "unit": "W"}}}
    },
    "xiaomi.wifispeaker.x08c":{
        "device_type": ['media_player'],
        "mapping":{"mp_play":{"siid":2,"aiid":2},"mp_pause":{"siid":2,"aiid":1},"mp_next":{"siid":2,"aiid":3},"mp_previous":{"siid":2,"aiid":4},"mp_sound_mode":{"siid":3,"aiid":1},"playing_state":{"siid":2,"piid":1},"volume":{"siid":4,"piid":1}},
        "params":{"playing_state":{"playing":1,"pause":0},"volume":{"value_range":[5,100,5]},"mp_source":{"\u64ad\u653e\u79c1\u4eba\u7535\u53f0":{"siid":3,"aiid":3},"\u64ad\u653e\u97f3\u4e50":{"siid":3,"aiid":4},"\u505c\u6b62\u95f9\u949f":{"siid":6,"aiid":1}},"mp_sound_mode":{"\u4f60\u597d":0}}
    },
    "xiaomi.wifispeaker.s12":{
        "device_type": ['media_player'],
        "mapping":{"mp_play":{"siid":4,"aiid":2},"mp_pause":{"siid":4,"aiid":1},"mp_next":{"siid":4,"aiid":3},"mp_previous":{"siid":4,"aiid":4},"mp_sound_mode":{"siid":5,"aiid":1},"playing_state":{"siid":4,"piid":1},"volume":{"siid":2,"piid":1}},
        "params":{"playing_state":{"playing":1,"pause":0},"volume":{"value_range":[1,100,1]},"mp_source":{"\u64ad\u653e\u79c1\u4eba\u7535\u53f0":{"siid":5,"aiid":4},"\u64ad\u653e\u97f3\u4e50":{"siid":5,"aiid":2},"\u505c\u6b62\u95f9\u949f":{"siid":6,"aiid":1}},"mp_sound_mode":{"\u4f60\u597d":0}}
    },
}