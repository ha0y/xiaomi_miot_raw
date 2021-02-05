import json
import re
from dataclasses import dataclass
import logging
from .const import MAP

_LOGGER = logging.getLogger(__name__)

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

SUPPORTED = {vv for v in MAP.values() for vv in v}

def get_type_by_mitype(mitype:str):
    for k,v in MAP.items():
        if mitype in v:
            return k
    return None

translate = {"on":"switch_status", "fan_level":"speed", "horizontal_swing":"oscillate"}

class MiotAdapter:
    def __init__(self, spec: dict):
        self.spec = spec
        self.services = {}
        self.devtypeset = set()
        try:
            self.init_all_services()
        except:
            pass

    def init_all_services(self) -> None:
        for s in self.spec['services']:
            if (n := name_by_type(s['type'])) in SUPPORTED:
                self.devtypeset.add(get_type_by_mitype(n))
            if not self.services.get(name_by_type(s['type'])):
                self.services[name_by_type(s['type'])] = Service(
                    s['iid'], s['type'], s['description'], self.get_prop_by_siid(s), name_by_type(s['type']))
            else:
                for i in range(2,5):
                    if not self.services.get(f"{name_by_type(s['type'])}_{i}"):
                        self.services[f"{name_by_type(s['type'])}_{i}"] = Service(
                            s['iid'], s['type'], s['description'], self.get_prop_by_siid(s), f"{name_by_type(s['type'])}_{i}")
                        break

    @property
    def get_all_services(self):
        return self.services

    @property
    def mitype(self):
        return name_by_type(self.spec.get('type'))

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
        try:
            # ret = []
            ret = {}
            for p in propdict.values():
                did = translate.get(p.newid) or p.newid
                ret[did] = {
                    "siid": p.siid,
                    "piid": p.piid
                }
            return ret
        except:
            return {}

    def get_mapping_by_siid(self, siid: int):
        try:
            return self.get_mapping(self.get_prop_by_siid(siid=siid))
        except:
            return None

    def get_mapping_by_snewid(self, newid: str):
        try:
            return self.get_mapping(self.services.get(newid).properties)
        except AttributeError:
            return None

    def get_params(self, propdict: dict = {}, devtype = ""):
        devtype = get_type_by_mitype(devtype)
        try:
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

            if p := propdict.get('mode'):
                if vl := p.vlist:
                    lst = {item['description']: item['value'] for item in vl}
                    ret['mode'] = lst

            # print(devtype)
            if devtype == 'light':
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

            if devtype == 'cover':
                if p := propdict.get('motor_control'):
                    dct = {}
                    if vl := p.vlist:
                        for item in vl:
                            if 'pause' in item['description'].lower() or \
                                'stop' in item['description'].lower() or \
                                    '停' in item['description']:
                                        dct['stop'] = item['value']
                            if 'up' in item['description'].lower() or \
                                '升' in item['description']:
                                    dct['open'] = item['value']
                            if 'down' in item['description'].lower() or \
                                '降' in item['description']:
                                    dct['close'] = item['value']
                        ret['motor_control'] = dct
                        for item in ['open','close','stop']:
                            if item not in dct:
                                _LOGGER.error(f"No {item} was found in motor_control.")
                if p := propdict.get('current_position'):
                    if vr := p.vrange:
                        ret['current_position'] = {
                            'value_range': vr
                        }
                if p := propdict.get('target_position'):
                    if vr := p.vrange:
                        ret['target_position'] = {
                            'value_range': vr
                        }

            if devtype == 'fan':
                if p := propdict.get('mode'):
                    if vl := p.vlist:
                        if not ret.get('speed'):
                            ret['speed'] = ret.pop('mode')

            #TODO zhimi.fan.fa1 has both fan_level and mode
                if p := propdict.get('horizontal_swing'):
                    ret['oscillate'] = {
                        True: True,
                        False: False
                    }

            if p := propdict.get('target_humidity'):
                if vr := p.vrange:
                    ret['target_humidity'] = {
                        'value_range': vr
                    }
            return ret
        except:
            return {}

    def get_params_by_siid(self, siid: int):
        return self.get_params(self.get_prop_by_siid(siid=siid))

    def get_params_by_snewid(self, newid: str):
        try:
            return self.get_params(self.services.get(newid).properties, self.services.get(newid).newid)
        except AttributeError:
            return None

    def get_all_mapping(self):
        ret={}
        for service in self.services.values():
            if (nid := service.newid) in SUPPORTED:
                ret[nid]=self.get_mapping_by_snewid(nid)
        return ret

    def get_all_params(self):
        ret={}
        has_main = False
        for service in self.services.values():
            if (nid := service.newid) in SUPPORTED:
                if not ret.get(nid):
                    ret[nid]=self.get_params_by_snewid(nid)
                    if nid == self.mitype and not has_main:
                        ret[nid]['main'] = True
                        has_main = True
        if not has_main:
            try:
                ret['switch']['main'] = True
            except KeyError:
                _LOGGER.error("识别不出主设备，请手动指定")
        return ret

    def get_all_devtype(self):
        return list(self.devtypeset)

if __name__ == '__main__':

    j = """"""

    jj = json.loads(j)


    adapter = MiotAdapter(jj)
    dt = adapter.devtype
    mt = adapter.mitype

    # p = adapter.get_mapping_by_snewid(dt) or adapter.get_mapping_by_snewid(mt)
    # p = adapter.get_mapping_by_siid(2)
    # pp = adapter.get_params_by_snewid(dt) or adapter.get_params_by_snewid(mt)
    # print(p)
    # print(pp)
    print(adapter.devtype)
    print(json.dumps(adapter.get_all_mapping()))
    print(json.dumps(adapter.get_all_params()))
    print(json.dumps(adapter.get_all_devtype()))