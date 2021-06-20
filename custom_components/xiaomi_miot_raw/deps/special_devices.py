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
    "lumi.sensor_motion.v2": {
        "device_type":['sensor'],
        "mapping":{"motion":{"key":"device_log","type":"prop"}},
        "params":{"event_based":True}
    },
    "lumi.motion.bmgl01": {
        "device_type":['sensor'],
        "mapping":{"motion":{"key":"device_log","type":"prop"}},
        "params":{"event_based":True}
    },
    "lumi.sensor_motion.aq2": {
        "device_type":['sensor'],
        "mapping":{"motion":{"key":"device_log","type":"prop"}},
        "params":{"event_based":True}
    },
    "cuco.plug.cp2":{
        "device_type": ['switch'],
        "mapping": {"switch": {"switch_status": {"siid": 2, "piid": 1}}},
        "params": {"switch": {"switch_status": {"power_on": True, "power_off": False}, "main": True}}
    },
    "degree.lunar.smh013": {
        "device_type": ['switch', 'sensor'],
        "mapping": {"sleep_monitor":{"sleep_state":{"siid":2,"piid":1},"realtime_heart_rate":{"siid":4,"piid":10},"realtime_breath_rate":{"siid":4,"piid":11},"realtime_sleepstage":{"siid":4,"piid":12}},"switch":{"switch_status":{"siid":4,"piid":15}}},
        "params": {"sleep_monitor":{"sleep_state":{"access":5,"format":"uint8","unit":None,"value_list":{"Out of Bed":0,"Awake":1,"Light Sleep":3,"Deep Sleep":4,"Rapid Eye Movement":2}},"realtime_heart_rate":{"unit":"bpm"},"realtime_breath_rate":{"unit":"/min"},"main":True},"switch":{"switch_status":{"power_on":True,"power_off":False}}}
    },
    "hhcc.plantmonitor.v1": {
        "device_type": ['sensor'],
        "mapping": {"plant_monitor":{"temperature":{"siid":3,"piid":2},"relative_humidity":{"siid":2,"piid":1},"soil_ec":{"siid":2,"piid":2},"illumination":{"siid":2,"piid":3}}},
        "params": {"plant_monitor": {"temperature": {"access": 5, "format": "float", "unit": "celsius"}, "relative_humidity": {"access": 5, "format": "float", "unit": "percentage", "value_range": [0, 100, 1]}, "soil_ec": {"access": 5, "format": "uint16", "unit": "µS/cm", "value_range": [0, 5000, 1]}, "illumination": {"access": 5, "format": "float", "unit": "lux", "value_range": [0, 10000, 1]}, "main": True}}
    },
    "zhimi.heater.na1": {
        "device_type": ['climate', 'switch', 'light', 'lock'],
        "mapping": {"heater": {"fault": {"siid": 2, "piid": 1}, "switch_status": {"siid": 2, "piid": 2}, "speed": {"siid": 2, "piid": 3}, "horizontal_swing": {"siid": 2, "piid": 4}}, "indicator_light": {"brightness": {"siid": 6, "piid": 1}}, "physical_controls_locked": {"physical_controls_locked": {"siid": 7, "piid": 1}}, "switch": {"switch_status":{"siid":3,"piid":1}}, "switch_2": {"switch_status":{"siid":8,"piid":3}}},
        "params": {"heater": {"switch_status": {"power_on": True, "power_off": False}, "fault": {"No faults": 0}, "horizontal_swing":{"off":0,"on":1}, "speed": {"High": 1, "Low": 2}, "main": True},"switch":{"switch_status":{"power_on":True,"power_off":False}}, "indicator_light": {"brightness": {"value_range": [0, 2, 1]}}, "physical_controls_locked": {"enabled": False}, "switch_2":{"switch_status":{"power_on": True,"power_off": False}}}
    },
    "lumi.gateway.mgl03": {
        "device_type": ['switch'],
        "mapping": {"switch": {"switch_status": {"siid": 3, "piid": 22}}},
        "params": {"switch": {"switch_status": {"power_on": 2, "power_off": 0}, "main": True}}
    },
    "zimi.plug.zncz01": {
        "device_type": ['switch', 'light', 'sensor'],
        "mapping": {"switch": {"switch_status": {"siid": 2, "piid": 1}, "working_time": {"siid": 2, "piid": 2}}, "power_consumption": {"electric_power": {"siid": 3, "piid": 1}, "power_consumption": {"siid": 3, "piid": 2}}, "indicator_light": {"switch_status": {"siid": 4, "piid": 1}}},
        "params": {"switch": {"switch_status": {"power_on": True, "power_off": False}, "working_time": {"access": 5, "format": "uint32", "unit": "minutes", "value_range": [0, 30, 1]}, "main": True}, "power_consumption": {"electric_power":{"value_ratio": 0.01, "unit": "W"}}, "indicator_light": {"switch_status": {"power_on": True, "power_off": False}}}
    },
}


LOCK_PRM = {
    "device_type": ['sensor'],
    "mapping":'{"door":{"key":7,"type":"event"},"lock":{"key":11,"type":"event"}}',
    "params":'{"event_based":true}'
}
