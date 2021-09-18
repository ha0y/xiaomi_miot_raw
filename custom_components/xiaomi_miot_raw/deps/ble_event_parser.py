import re
from datetime import datetime

DOOR_EVENTS = {
    0x00: "开门",
    0x01: "关门",
    0x02: "超时未关",
    0x03: "敲门",
    0x04: "撬门",
    0x05: "门卡住",
}

BLE_LOCK_ACTION = {
    0b0000: "门外开锁",
    0b0001: "上提把手锁门",
    0b0010: "开启反锁",
    0b0011: "解除反锁",
    0b0100: "门内开锁",
    0b0101: "门内上锁",
    0b0110: "开启童锁",
    0b0111: "关闭童锁",
    0b1000: "门外上锁",
    0b1111: "异常",
}

BLE_LOCK_METHOD = {
    0b0000: "蓝牙",
    0b0001: "密码",
    0b0010: "指纹",
    0b0011: "钥匙",
    0b0100: "转盘",
    0b0101: "NFC",
    0b0110: "一次性密码",
    0b0111: "双重验证",
    0b1001: "Homekit",
    0b1000: "胁迫",
    0b1010: "人工",
    0b1011: "自动",
    0b1111: "异常",
}

BLE_LOCK_ERROR = {
    0xC0DE0000: "错误密码频繁开锁",
    0xC0DE0001: "错误指纹频繁开锁",
    0xC0DE0002: "操作超时（密码输入超时）",
    0xC0DE0003: "撬锁",
    0xC0DE0004: "重置按键按下",
    0xC0DE0005: "错误钥匙频繁开锁",
    0xC0DE0006: "钥匙孔异物",
    0xC0DE0007: "钥匙未取出",
    0xC0DE0008: "错误NFC频繁开锁",
    0xC0DE0009: "超时未按要求上锁",
    0xC0DE000A: "多种方式频繁开锁失败",
    0xC0DE000B: "人脸频繁开锁失败",
    0xC0DE000C: "静脉频繁开锁失败",
    0xC0DE000D: "劫持报警",
    0xC0DE000E: "布防后门内开锁",
    0xC0DE000F: "掌纹频繁开锁失败",
    0xC0DE0010: "保险箱被移动",
    0xC0DE1000: "电量低于10%",
    0xC0DE1001: "电量低于5%",
    0xC0DE1002: "指纹传感器异常",
    0xC0DE1003: "配件电池电量低",
    0xC0DE1004: "机械故障",
    0xC0DE1005: "锁体传感器故障",
}

BUTTON_EVENTS = {
    0: "single press",
    1: "double press",
    2: "long press",
    3: "triple press",
}

class EventParser:
    def __init__(self, data):
        self.data = re.sub(r'\[\"(.*)\"\]', r'\1', data)

    def __int__(self):
        return int.from_bytes(bytes.fromhex(self.data), 'little')

    def __getitem__(self, key):
        return bytes.fromhex(self.data)[key]

    @property
    def timestamp(self):
        return 0

    @property
    def friendly_time(self):
        return datetime.fromtimestamp(self.timestamp).isoformat(sep=' ')


class BleDoorParser(EventParser):    #0x0007, 7
    @property
    def event_id(self):
        return self[0]

    @property
    def event_name(self):
        return DOOR_EVENTS[self[0]]

    @property
    def timestamp(self):
        if len(self.data) != 10:
            return None
        else:
            return int.from_bytes(self[1:5], 'little')

class BleLockParser(EventParser):    #0x000b, 11
    @property
    def action_id(self):
        return self[0] & 0x0F

    @property
    def method_id(self):
        return self[0] >> 4

    @property
    def action_name(self):
        return BLE_LOCK_ACTION[self[0] & 0x0F]

    @property
    def method_name(self):
        return BLE_LOCK_METHOD[self[0] >> 4]

    @property
    def key_id(self):
        return int.from_bytes(self[1:5], 'little')

    @property
    def error_name(self):
        return BLE_LOCK_ERROR.get(self.key_id)

    @property
    def key_id_short(self):
        if self.error_name is None and self.method_id > 0:
            return self.key_id & 0xFFFF
        elif self.error_name:
            return hex(self.key_id)
        else:
            return self.key_id

    @property
    def timestamp(self):
        return int.from_bytes(self[5:9], 'little')

class BleMotionWithIlluParser(EventParser): #0x000f, 15
    @property
    def illumination(self):
        return int(self.data)
    
class BleButtonParser(EventParser):  #0x1001, 4097
    @property
    def action_id(self):
        return self[2]

    @property
    def action_name(self):
        if self[2] in BUTTON_EVENTS:
            return BUTTON_EVENTS[self[2]]
        else:
            return ""

class TimestampParser(EventParser):
    @property
    def timestamp(self):
        return int(self.data.split('[')[1].split(',')[0])

class ZgbIlluminationParser(EventParser):
    @property
    def illumination(self):
        try:
            return int(self.data.split('[')[3].split(']')[0])
        except ValueError:
            return None
if __name__ == '__main__':
    a = TimestampParser(r'''["[1617026674,[\"event.motion\",[]]]"]''')
    # print(a.event_id)
    print(a.timestamp)
