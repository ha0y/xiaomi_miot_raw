import json
import re
from dataclasses import dataclass

@dataclass
class Property:
    siid        :int
    piid        :int
    type_       :str
    description :str
    format_     :bool
    access      :list
    newid       :str
    unit        :str
    vlist       :list
    vrange      :list

@dataclass
class Service:
    siid        :int
    type_       :str
    description :str
    properties  :dict
    newid       :str

def name_by_type(typ):
    arr = f'{typ}:::'.split(':')
    nam = arr[3] or ''
    nam = re.sub(r'\W+', '_', nam)
    return nam

def get_type_by_mitype(mitype:str):
    map = {
        "sensor": [
            "air-monitor",
            "water-purifier",
            "cooker",
            "pressure-cooker",
            "induction-cooker",
        ],
        "switch": [
            "switch",
            "outlet",
        ],
        "light": [
            "light",
        ],
        "fan": [
            "fan",
            "ceiling-fan",
        ],
        "cover": [
            "curtain",
            "airer",
        ]
    }
    for k,v in map.items():
        if mitype in v:
            return k
    return None

translate = {"on":"switch_status", "fan_level":"speed"}

class MiotAdapter:
    def __init__(self, spec: dict):
        self.spec = spec
        self.services = {}
        try:
            self.init_all_services()
        except:
            pass
    
    def init_all_services(self) -> None:
        for s in self.spec['services']:
            self.services[name_by_type(s['type'])] = Service(
                s['iid'], s['type'], s['description'], self.get_prop_by_siid(s), name_by_type(s['type']))
                     
    @property
    def get_all_services(self):
        return self.services
    
    @property
    def devtype(self):
        return get_type_by_mitype(name_by_type(self.spec.get('type')))

    def get_service_by_id(self, id:int):
        for s in self.spec['services']:
            if s['iid'] == id:
                return s
        return None

    def get_prop_by_siid(self, service: dict = [], siid: int = None):
        if siid:
            service = self.get_service_by_id(siid)
        if not service :
            return None
        props = {}
        for p in service['properties']:
            props[name_by_type(p['type'])] = Property(service['iid'], 
                                                      p['iid'], p['type'],p['description'], p['format'], p['access'], name_by_type(p['type']),
                                                      p.get('unit'),
                                                      p.get('value-list'),
                                                      p.get('value-range'))

        
        return props

    def get_mapping(self, propdict: dict = {}):
        # ret = []
        ret = {}
        for p in propdict.values():
            did = translate.get(p.newid) or p.newid
            ret[did] = {
                "siid": p.siid,
                "piid": p.piid
            }
        return ret
    
    def get_mapping_by_siid(self, siid: int):
        return self.get_mapping(self.get_prop_by_siid(siid=siid))

    def get_mapping_by_snewid(self, newid: str):
        return self.get_mapping(self.services[newid].properties)

    def get_params(self, propdict: dict = {}):
        ret = {}
        
        if p := propdict.get('on'):
            if p.format_ == 'bool':
                ret['switch_status'] = {
                    'power_on': True,
                    'power_off': False
                }
            else:
                # TODO: will this happen?
                ret['switch_status'] = {
                    'power_on': True,
                    'power_off': False
                }
        if p := propdict.get('fan_level'):
            if vl := p.vlist:
                lst = {item['description']: item['value'] for item in vl}
                ret['speed'] = lst
            elif vr := p.vrange:
                lst = {
                    str(i):i for i in range(vr[0],vr[1]+1,vr[2])
                }
                ret['speed'] = lst
            else:    
                # TODO: will this happen?
                pass
        if p := propdict.get('brightness'):
            if vr := p.vrange:
                ret['brightness'] = {
                    'value_range': vr
                }
            else:
                # TODO: will this happen?
                pass
        if p := propdict.get('color_temperature'):
            if vr := p.vrange:
                ret['color_temperature'] = {
                    'value_range': vr
                }
            else:
                # TODO: will this happen?
                pass
        
        return ret

    def get_params_by_siid(self, siid: int):
        return self.get_params(self.get_prop_by_siid(siid=siid))

    def get_params_by_snewid(self, newid: str):
        return self.get_params(self.services[newid].properties)

if __name__ == '__main__':
    j = '''{ "type": "urn:miot-spec-v2:device:light:0000A001:leshi-wyfan:1", "description": "Light", "services": [ { "iid": 1, "type": "urn:miot-spec-v2:service:device-information:00007801:leshi-wyfan:1", "description": "Device Information", "properties": [ { "iid": 1, "type": "urn:miot-spec-v2:property:manufacturer:00000001:leshi-wyfan:1", "description": "Device Manufacturer", "format": "string", "access": [ "read" ] }, { "iid": 2, "type": "urn:miot-spec-v2:property:model:00000002:leshi-wyfan:1", "description": "Device Model", "format": "string", "access": [ "read" ] }, { "iid": 3, "type": "urn:miot-spec-v2:property:serial-number:00000003:leshi-wyfan:1", "description": "Device Serial Number", "format": "string", "access": [ "read" ] }, { "iid": 4, "type": "urn:miot-spec-v2:property:firmware-revision:00000005:leshi-wyfan:1", "description": "Current Firmware Version", "format": "string", "access": [ "read" ] } ] }, { "iid": 2, "type": "urn:miot-spec-v2:service:light:00007802:leshi-wyfan:1", "description": "Light", "properties": [ { "iid": 1, "type": "urn:miot-spec-v2:property:on:00000006:leshi-wyfan:1", "description": "Switch Status", "format": "bool", "access": [ "read", "write", "notify" ] }, { "iid": 2, "type": "urn:miot-spec-v2:property:brightness:0000000D:leshi-wyfan:1", "description": "Brightness", "format": "uint8", "access": [ "read", "write", "notify" ], "unit": "percentage", "value-range": [ 1, 100, 1 ] }, { "iid": 3, "type": "urn:miot-spec-v2:property:color-temperature:0000000F:leshi-wyfan:1", "description": "Color Temperature", "format": "uint32", "access": [ "read", "write", "notify" ], "unit": "kelvin", "value-range": [ 3000, 6400, 1 ] } ] }, { "iid": 3, "type": "urn:miot-spec-v2:service:fan:00007808:leshi-wyfan:1", "description": "Fan", "properties": [ { "iid": 1, "type": "urn:miot-spec-v2:property:on:00000006:leshi-wyfan:1", "description": "Switch Status", "format": "bool", "access": [ "read", "write", "notify" ] }, { "iid": 2, "type": "urn:miot-spec-v2:property:fan-level:00000016:leshi-wyfan:1", "description": "Fan Level", "format": "uint8", "access": [ "read", "write", "notify" ], "unit": "none", "value-list": [ { "value": 1, "description": "Low" }, { "value": 2, "description": "Medium" }, { "value": 3, "description": "High" } ] }, { "iid": 3, "type": "urn:miot-spec-v2:property:motor-reverse:00000072:leshi-wyfan:1", "description": "Motor Reverse", "format": "bool", "access": [ "read", "write", "notify" ], "unit": "none" } ] } ] }'''

    jj = json.loads(j)

    
    adapter = MiotAdapter(jj)
    dt = adapter.devtype
    
    p = adapter.get_mapping_by_snewid(dt)
    # p = adapter.get_mapping_by_siid(2)
    pp = adapter.get_params_by_snewid(dt)
    print(p)
    print(pp)
    print(adapter.devtype)