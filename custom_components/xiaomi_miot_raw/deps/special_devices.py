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
        "mapping":{"motion":{"key":15, "type":"event"}},
        "params":{"event_based":True}
    },
    "lumi.sensor_motion.aq2": {
        "device_type":['sensor'],
        "mapping":{"motion":{"key":"device_log","type":"prop"}},
        "params":{"event_based":True}
    },
    "cuco.plug.cp2":{
        "device_type": ['switch','sensor'],
        "mapping": {"switch":{"switch_status":{"siid":2,"piid":1}},"power_consumption":{"power_consumption":{"siid":2,"piid":2},"voltage":{"siid":2,"piid":3},"electric_current":{"siid":2,"piid":4},"countdown_time":{"siid":2,"piid":5}}},
        "params": {"switch":{"switch_status":{"power_on":True,"power_off":False},"main":True},"power_consumption":{"power_consumption":{"access":5,"format":"uint16","unit":"kWh","value_range":[0,65535,1],"value_ratio": 0.01},"voltage":{"access":5,"format":"uint16","unit":"V","value_range":[0,3000,1],"value_ratio": 0.1},"electric_current":{"access":1,"format":"uint16","unit":"A","value_range":[0,65535,1],"value_ratio": 0.001},"countdown_time":{"access":7,"format":"uint16","unit":"minutes","value_range":[0,1440,1]}}, 'max_properties': 1}
    },
    "cuco.plug.cp1m":{
        "device_type": ['switch','sensor'],
        "mapping": {"switch":{"switch_status":{"siid":2,"piid":1}},"power_consumption":{"power_consumption":{"siid":2,"piid":2},"voltage":{"siid":2,"piid":3},"electric_current":{"siid":2,"piid":4}}},
        "params": {"switch":{"switch_status":{"power_on":True,"power_off":False},"main":True},"power_consumption":{"power_consumption":{"access":5,"format":"uint16","unit":"kWh","value_range":[0,65535,1],"value_ratio": 0.01},"voltage":{"access":5,"format":"uint16","unit":"V","value_range":[0,3000,1],"value_ratio": 0.1},"electric_current":{"access":1,"format":"uint16","unit":"A","value_range":[0,65535,1],"value_ratio": 0.001}}, 'max_properties': 1}
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
    "lumi.acpartner.mcn04": {
        "device_type": ['climate', 'light', 'sensor'],
        "mapping": {"air_conditioner": {"switch_status": {"siid": 3, "piid": 1}, "mode": {"siid": 3, "piid": 2}, "fault": {"siid": 3, "piid": 3}, "target_temperature": {"siid": 3, "piid": 4}, "speed": {"siid": 4, "piid": 2}, "vertical_swing": {"siid": 4, "piid": 4}}, "power_consumption": {"power_consumption": {"siid": 7, "piid": 1}, "electric_power": {"siid": 7, "piid": 2}}, "power_10A_consumption": {"power_consumption": {"siid": 7, "piid": 3}, "electric_power": {"siid": 7, "piid": 4}}, "indicator_light": {"indicator_light": {"siid": 9, "piid": 1}, "effective_time": {"siid": 9, "piid": 2}}},
        "params": {"air_conditioner": {"switch_status": {"power_on": True, "power_off": False}, "fault": {"No Faults": 0}, "mode": {"Cool": 0, "Heat": 1, "Auto": 2, "Fan": 3, "Dry": 4}, "target_temperature": {"value_range": [16, 30, 1]}, "speed": {"Auto": 0, "Low": 1, "Medium": 2, "High": 3}, "main": True}, "power_consumption": {"electric_power":{"unit": "W"}}, "power_10A_consumption": {"electric_power":{"unit": "W"}},"indicator_light": {"enabled": False, "effective_time": {"access": 7, "format": "uint32", "unit": None, "value_range": [1, 991378198, 1]}}}
    },
    "lumi.airrtc.tcpecn01": {
        "device_type": ['climate', 'switch'],
        "mapping": {"air_conditioner": {"switch_status": {"siid": 2, "piid": 1}, "mode": {"siid": 2, "piid": 2}, "target_temperature": {"siid": 2, "piid": 3}, "speed": {"siid": 3, "piid": 1}}, "switch": {"switch_status": {"siid": 2, "piid": 1}}},
        "params": {"air_conditioner": {"switch_status": {"power_on": True, "power_off": False}, "mode": {"Cool": 1, "Heat": 2}, "target_temperature": {"value_range": [17, 30, 1]}, "main": True, "speed": {"Auto": 0, "Low": 1, "Medium": 2, "High": 3}}, "switch": {"switch_status": {"power_on": True, "power_off": False}}}
    },
    "dmaker.fan.1e": {
        "device_type": ['fan'],
        "mapping": {"fan": {"switch_status": {"siid": 2, "piid": 1}, "speed": {"siid": 2, "piid": 2}, "mode": {"siid": 2, "piid": 3}, "oscillate": {"siid": 2, "piid": 4}, "horizontal_angle": {"siid": 2, "piid": 5}, "stepless_speed": {"siid": 8, "piid": 1}, "motor_control": {"siid": 6, "piid": 1}}, "indicator_light": {"switch_status": {"siid": 4, "piid": 1}}, "physical_controls_locked": {"physical_controls_locked": {"siid": 7, "piid": 1}}, "a_l": {"off_delay_time_toggle": {"siid": 3, "aiid": 1}, "dm_service_toggle_mode": {"siid": 8, "aiid": 1}, "dm_service_loop_gear": {"siid": 8, "aiid": 2}}},
        "params": {"fan": {"switch_status": {"power_on": True, "power_off": False}, "speed": {"Level1": 1, "Level2": 2, "Level3": 3, "Level4": 4}, "mode": {"Straight Wind": 0, "Natural Wind": 1}, "oscillate": {"True": True, "False": False}, "horizontal_angle": {"access": 7, "format": "uint16", "unit": None, "value_list": {"30": 30, "60": 60, "90": 90, "120": 120, "140": 140}}, "main": True, "stepless_speed": {"value_range": [1, 100, 1]}, "motor_control": {"left": 1, "right": 2}}, "indicator_light": {"switch_status": {"power_on": True, "power_off": False}}, "physical_controls_locked": {"enabled": False}}
    },
    "cgllc.airm.cgdn1": {
        "device_type": ['sensor', 'fan'],
        "mapping": {"environment": {"relative_humidity": {"siid": 3, "piid": 1}, "pm2_5_density": {"siid": 3, "piid": 4}, "pm10_density": {"siid": 3, "piid": 5}, "temperature": {"siid": 3, "piid": 7}, "co2_density": {"siid": 3, "piid": 8}}, "settings": {"start_time": {"siid": 9, "piid": 2}, "end_time": {"siid": 9, "piid": 3}, "monitoring_frequency": {"siid": 9, "piid": 4}, "screen_off": {"siid": 9, "piid": 5}, "device_off": {"siid": 9, "piid": 6}, "tempature_unit": {"siid": 9, "piid": 7}}, "a_l": {"settings_set_start_time": {"siid": 9, "aiid": 2}, "settings_set_end_time": {"siid": 9, "aiid": 3}, "settings_set_frequency": {"siid": 9, "aiid": 4}, "settings_set_screen_off": {"siid": 9, "aiid": 5}, "settings_set_device_off": {"siid": 9, "aiid": 6}, "settings_set_temp_unit": {"siid": 9, "aiid": 7}}},
        "params": {"environment": {"relative_humidity": {"access": 5, "format": "uint8", "unit": "percentage", "value_range": [0, 100, 1]}, "pm2_5_density": {"access": 5, "format": "uint16", "unit": "\u03bcg/m3", "value_range": [0, 1000, 1]}, "pm10_density": {"access": 5, "format": "uint16", "unit": "\u03bcg/m3", "value_range": [0, 1000, 1]}, "temperature": {"access": 5, "format": "float", "unit": "celsius", "value_range": [-30, 100, 1e-05]}, "co2_density": {"access": 5, "format": "uint16", "unit": "ppm", "value_range": [0, 9999, 1]}, "main": True}, "settings": {"start_time": {"access": 7, "format": "int32", "value_range": [0, 2147483647, 1]}, "end_time": {"access": 7, "format": "int32", "value_range": [0, 2147483647, 1]}, "monitoring_frequency": {"access": 7, "format": "uint16", "unit": "seconds", "value_list": {"Second": 600, "Null": 0}}, "screen_off": {"access": 7, "format": "uint16", "unit": "seconds", "value_list": {"Second": 300, "Null": 0}}, "device_off": {"access": 7, "format": "int8", "unit": "minutes", "value_list": {"Minute": 60, "Null": 0}}, "tempature_unit": {"access": 7, "format": "string"}}, 'max_properties': 8}
    },
    "yeelink.remote.remote": {
        "device_type":['sensor'],
        "mapping":{"button":{"key":4097,"type":"event"}},
        "params":{"event_based":True}
    },
    "ateai.mosq.dakuo": {
        "device_type": ["sensor", "fan"],
        "mapping": {"mosquito_dispeller": {"switch_status": {"siid": 6, "piid": 1},"mode":{"siid": 6, "piid": 2}}, "repellent_liquid": {"liquid_left": {"siid": 5, "piid": 1}}, "a_l": {"repellent_liquid_reset_liquid": {"siid": 5, "aiid": 1}}},
        "params": {"mosquito_dispeller":{"switch_status":{"power_on":1,"power_off":0},"main":True,"mode":{"Strong":0,"Baby":1}},"repellent_liquid":{"liquid_left":{"access":5,"format":"uint8","unit":"percentage","value_range":[0,100,1]}}}
    },
}
