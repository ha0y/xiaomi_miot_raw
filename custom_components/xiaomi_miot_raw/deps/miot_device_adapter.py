import json
import re
from dataclasses import dataclass
import logging
from .const import MAP
from .special_devices import SPECIAL_DEVICES

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
    actions     :list

@dataclass
class Action:
    siid        :int
    aiid        :int
    type_       :str
    description :str
    in_         :list
    out_        :list

def get_id_by_instance(s:dict):
    if 'type' not in s:
        return ''
    try:
        type_ = f'{s["type"]}:::'.split(':')[3]
        r = re.sub(r'\W+', '_', type_)
        if 'description' in s:
            if r == 'switch' and 'USB' in s['description']:
                r = 'switch_usb'
        return r
    except Exception as ex:
        _LOGGER.error(ex)
        return ''

ACCESS_READ = 0b001
ACCESS_WRITE = 0b010
ACCESS_NOTIFY = 0b100

CUSTOM_SERVICES = {'custom_service', 'private_service', 'dm_service'}
SUPPORTED = {vv for v in MAP.values() for vv in v}.union(CUSTOM_SERVICES)

def get_type_by_mitype(mitype:str):
    if mitype == "fan_control":
        return "fan_control"
    for k,v in MAP.items():
        if mitype in v:
            return k
    return None

translate = {"on":"switch_status", 
             "fan_level":"speed", 
             "horizontal_swing":"oscillate", 
             "speed_level":"stepless_speed", 
             "stepless_fan_level":"stepless_speed"}

def get_range_by_list(value_list: list):
    l = [item['value'] for item in value_list]
    l.sort()
    if len(l) <= 1:
        _LOGGER.error(f"Wrong value list: {value_list}")
        return None
    else:
        d = l[1] - l[0]
        for i in range(2, len(l)):
            if l[i] - l[i-1] != d:
                _LOGGER.error(f"Cannot convert value list {value_list} to range: Not a arithmetic progression!")
                return None
        return [l[0], l[-1], d]


class MiotAdapter:
    def __init__(self, spec: dict):
        self.spec = spec
        self.services = {}
        self.devtypeset = set()
        try:
            self.init_all_services()
        except Exception as ex:
            _LOGGER.error(ex)

    def init_all_services(self) -> None:
        for s in self.spec['services']:
            sid = get_id_by_instance(s)
            if sid in SUPPORTED:
                if sid != 'fan_control' and sid not in CUSTOM_SERVICES:
                    self.devtypeset.add(get_type_by_mitype(sid))
            if not self.services.get(sid):
                self.services[sid] = Service(
                    s['iid'], s['type'], s['description'], self.get_prop_by_siid(s), sid, s.get('actions') or [])
            else:
                for i in range(2,9):
                    if not self.services.get(f"{sid}_{i}"):
                        self.services[f"{sid}_{i}"] = Service(
                            s['iid'], s['type'], s['description'], self.get_prop_by_siid(s), f"{sid}_{i}", s.get('actions') or [])
                        break

    @property
    def get_all_services(self):
        return self.services

    @property
    def mitype(self):
        return get_id_by_instance(self.spec)

    @property
    def devtype(self):
        return get_type_by_mitype(self.mitype)

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
        if 'properties' not in service:
            return None
        props = {}
        for p in service['properties']:
            props[get_id_by_instance(p)] = Property(service['iid'],
                                                      p['iid'], p['type'],p['description'], p['format'], p['access'], get_id_by_instance(p),
                                                      p.get('unit'),
                                                      p.get('value-list'),
                                                      p.get('value-range'))

        return props

    def get_action_by_siid(self, service: dict = [], siid: int = None):
        if siid:
            service = self.get_service_by_id(siid)
        if not service :
            return None
        actions = {}
        for a in service.get('actions') or []:
            actions[get_id_by_instance(a)] = Action(
                service['iid'],
                a['iid'],
                a['type'],
                a['description'],
                a.get('in'),
                a.get('out')
            )

        return actions

    def get_mapping(self, propdict: dict = {}, devtype = ""):
        try:
            if not propdict:
                return None
            ret = {}
            for p in propdict.values():
                did = translate.get(p.newid) or p.newid
                ret[did] = {
                    "siid": p.siid,
                    "piid": p.piid
                }
            if devtype == 'fan':
                # if 'speed' not in ret and 'mode' in ret:
                #     ret['speed'] = ret.pop('mode')
                if 'horizontal_swing' in ret:
                    ret['oscillate'] = ret.pop('horizontal_swing')
                elif 'vertical_swing' in ret:
                    ret['oscillate'] = ret.pop('vertical_swing')
            if devtype in ('humidifier', 'dehumidifier') and 'mode' not in ret and 'speed' in ret:
                # deerma.humidifier.mjjsq
                ret['mode'] = ret.pop('speed')
            if devtype == 'cover':
                if 'current_position' in ret and 'target_position' not in ret:
                    ret['target_position'] = ret['current_position']
                elif 'target_position' in ret and 'current_position' not in ret:
                    ret['current_position'] = ret['target_position']
            return ret
        except Exception as ex:
            _LOGGER.error(ex)
            return {}

    def get_mapping_by_siid(self, siid: int):
        try:
            return self.get_mapping(self.get_prop_by_siid(siid=siid))
        except Exception as ex:
            _LOGGER.error(ex)
            return None

    def get_mapping_by_snewid(self, newid: str):
        try:
            return self.get_mapping(self.services.get(newid).properties, get_type_by_mitype(newid))
        except AttributeError:
            return None

    def get_params(self, propdict: dict = {}, devtype = ""):
        devtype = get_type_by_mitype(devtype)
        if not propdict:
            return None
        propdict2 = propdict.copy()
        try:
            ret = {}

            if p := propdict2.pop('on', None):
                if p.format_ == 'bool':
                    ret['switch_status'] = {
                        'power_on': True,
                        'power_off': False
                    }

            # 把某个 service 里的 property 单独提出来
            # 例如：晾衣架的烘干，新风机的辅热
            if p := propdict2.pop('dryer', None):
                if p.format_ == 'bool':
                    ret['dryer'] = {
                        'power_on': True,
                        'power_off': False
                    }

            if p := propdict2.pop('heater', None):
                if p.format_ == 'bool':
                    ret['heater'] = {
                        'power_on': True,
                        'power_off': False
                    }

            if p := propdict2.pop('fault', None):
                if vl := p.vlist:
                    lst = {item['description']: item['value'] for item in vl}
                    ret['fault'] = lst

            if p := propdict2.pop('fan_level', None):
                if vl := p.vlist:
                    lst = {item['description']: item['value'] for item in vl}
                    ret['speed'] = lst
                elif vr := p.vrange:
                    lst = {
                        str(i):i for i in range(vr[0],vr[1]+1,vr[2])
                    }
                    ret['speed'] = lst

            if p := propdict2.pop('speed_level', None): # dmaker stepless speed
                if vr := p.vrange:
                    ret['stepless_speed'] = {
                        'value_range': vr
                    }

            if p := propdict2.pop('stepless_fan_level', None): # zhimi stepless speed
                if vr := p.vrange:
                    ret['stepless_speed'] = {
                        'value_range': vr
                    }

            if p := propdict2.pop('mode', None):
                if vl := p.vlist:
                    lst = {item['description']: item['value'] for item in vl}
                    ret['mode'] = lst
                elif vr := p.vrange:
                    lst = {
                        str(i):i for i in range(vr[0],vr[1]+1,vr[2])
                    }
                    ret['mode'] = lst
            if p := propdict2.pop('target_temperature', None):
                if vr := p.vrange:
                    ret['target_temperature'] = {
                        'value_range': vr
                    }

            if p := propdict2.pop('drying_level', None):
                if vl := p.vlist:
                    lst = {item['description']: item['value'] for item in vl}
                    ret['drying_level'] = lst

            if p := propdict2.pop('status', None):
                if vl := p.vlist:
                    lst = {item['description']: item['value'] for item in vl}
                    ret['status'] = lst

            # print(devtype)
            if devtype == 'light':
                if p := propdict2.pop('brightness', None):
                    if vr := p.vrange:
                        ret['brightness'] = {
                            'value_range': vr
                        }
                    elif vl := p.vlist:
                        ret['brightness'] = {
                            'value_range': get_range_by_list(vl)
                        }
                if p := propdict2.pop('color_temperature', None):
                    if vr := p.vrange:
                        ret['color_temperature'] = {
                            'value_range': vr
                        }
                    else:
                        # TODO: will this happen?
                        pass

            if devtype == 'cover':
                if p := propdict2.pop('motor_control', None):
                    dct = {}
                    if vl := p.vlist:
                        for item in vl:
                            if 'pause' in item['description'].lower() or \
                                'stop' in item['description'].lower() or \
                                '停' in item['description']:
                                        dct['stop'] = item['value']
                            if 'up' in item['description'].lower() or \
                                'open' in item['description'].lower() or \
                                '升' in item['description']:
                                    dct['open'] = item['value']
                            if 'down' in item['description'].lower() or \
                                'close' in item['description'].lower() or \
                                '降' in item['description']:
                                    dct['close'] = item['value']
                        ret['motor_control'] = dct
                        for item in ['open','close','stop']:
                            if item not in dct:
                                _LOGGER.error(f"No {item} was found in motor_control.")
                if p := propdict2.pop('current_position', None):
                    if vr := p.vrange:
                        ret['current_position'] = {
                            'value_range': vr
                        }
                if p := propdict2.pop('target_position', None):
                    if vr := p.vrange:
                        ret['target_position'] = {
                            'value_range': vr
                        }
                if p := propdict2.pop('status', None):
                    dct = {}
                    if vl := p.vlist:
                        for item in vl:
                            if 'up' in item['description'].lower() or \
                                'open' in item['description'].lower() or \
                                '升' in item['description']:
                                    dct['open'] = item['value']
                            if 'down' in item['description'].lower() or \
                                'close' in item['description'].lower() or \
                                'dowm' in item['description'].lower() or \
                                '降' in item['description']:
                                    dct['close'] = item['value']
                        ret['motor_status'] = dct

            if devtype == 'fan':
                if p := propdict2.pop('mode', None):
                    if vl := p.vlist:
                        if not ret.get('speed'):
                            ret['speed'] = ret.pop('mode')

                #TODO zhimi.fan.fa1 has both fan_level and mode
                if p := propdict2.pop('horizontal_swing', None):
                    ret['oscillate'] = {
                        True: True,
                        False: False
                    }

            if devtype in ('humidifier', 'dehumidifier'):
                # deerma.humidifier.mjjsq
                if not ret.get('mode'):
                    ret['mode'] = ret.pop('speed')

            if devtype == 'media_player':
                if p := propdict2.pop('volume', None):
                    if vr := p.vrange:
                        ret['volume'] = {
                            'value_range': vr
                        }
                if p := propdict2.pop('playing_state', None):
                    if vl := p.vlist:
                        dct = {}
                        for item in vl:
                            if 'pause' in item['description'].lower() or \
                                'idle' in item['description'].lower():
                                    dct['pause'] = item['value']
                            if 'play' in item['description'].lower():
                                dct['playing'] = item['value']
                        ret['playing_state'] = dct

            if p := propdict2.pop('target_humidity', None):
                if vr := p.vrange:
                    ret['target_humidity'] = {
                        'value_range': vr
                    }
                # nwt.derh.330ef uses value list instead of range, convert it
                elif vl := p.vlist:
                    ret['target_humidity'] = {
                        'value_range': get_range_by_list(vl)
                    }

            if p := propdict2.pop('physical_controls_locked', None):
                ret['enabled'] = False
            if p := propdict2.pop('indicator_light', None):
                ret['enabled'] = False

            #####################

            for k,v in propdict2.items():
                r = {}
                acc = 0
                acc |= ACCESS_READ if 'read' in v.access else 0
                acc |= ACCESS_WRITE if 'write' in v.access else 0
                acc |= ACCESS_NOTIFY if 'notify' in v.access else 0
                r['access'] = acc
                r['format'] = v.format_
                r['unit'] = v.unit if v.unit != "none" else None
                if v.vlist:
                    r['value_list'] = dict([(a['description'], a['value']) for a in v.vlist])
                elif v.vrange:
                    r['value_range'] = v.vrange
                ret[k] = r

            return ret
        except Exception as ex:
            _LOGGER.error(ex)
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
                if (mp := self.get_mapping_by_snewid(nid)) is not None:
                    ret[nid]=mp

        if action_dict := self.get_all_actions():
            ret['a_l'] = action_dict
            self.devtypeset.add('fan')

        if 'fan_control' in ret:
            try:
                to_merge = next(t for t in ('air_conditioner', 'air_condition_outlet', 'hood') if t in ret)
                ret[to_merge] = {**ret[to_merge], **ret.pop('fan_control')}
            except Exception as ex:
                pass

        if 'speaker' in ret and 'play_control' in ret:
            ret['speaker'] = {**ret['speaker'], **ret.pop('play_control')}

        if 'ambient_light' in ret and 'ambient_light_custom' in ret:
            ret['ambient_light'] = {**ret['ambient_light'], **ret.pop('ambient_light_custom')}

        if 'screen' in ret and 'indicator_light' not in ret:
            ret['indicator_light'] = ret.pop('screen')

        if 'humidifier' in ret and 'environment' in ret:
            # deerma.humidifier.mjjsq target_humidity misplaced
            if 'target_humidity' in ret['environment']:
                ret['humidifier']['target_humidity'] = (ret['environment'].pop('target_humidity'))

        if 'fan' in ret:
            if 'stepless_speed' in ret.get('custom_service', {}):
                ret['fan']['stepless_speed'] = (ret['custom_service'].pop('stepless_speed'))
            if 'stepless_speed' in ret.get('dm_service', {}):
                ret['fan']['stepless_speed'] = (ret['dm_service'].pop('stepless_speed'))

        # 把某个 service 里的 property 单独提出来
        # 例如：晾衣架的烘干，新风机的辅热
        if 'airer' in ret:
            if 'dryer' in ret['airer']:
                ret.setdefault('dryer', {})
                ret['dryer'].update({'switch_status': ret['airer'].pop('dryer')})
                self.devtypeset.add('fan')
            if 'drying_level' in ret['airer']:
                ret.setdefault('dryer', {})
                ret['dryer'].update({'speed': ret['airer'].pop('drying_level')})

        if 'air_fresh' in ret:
            if 'heater' in ret['air_fresh']:
                ret.setdefault('air_fresh_heater', {})
                ret['air_fresh_heater'].update({'switch_status': ret['air_fresh'].pop('heater')})
                self.devtypeset.add('fan')

        for item in CUSTOM_SERVICES:
            ret.pop(item, None)
        return ret

    def get_all_params(self):
        ret={}
        has_main = False
        for service in self.services.values():
            if (nid := service.newid) in SUPPORTED:
                if not ret.get(nid):
                    if (prm := self.get_params_by_snewid(nid)) is not None:
                        ret[nid]=prm
                        if nid == self.mitype and not has_main:
                            ret[nid]['main'] = True
                            has_main = True

        if 'fan_control' in ret:
            try:
                to_merge = next(t for t in ('air_conditioner', 'air_condition_outlet', 'hood') if t in ret)
                ret[to_merge] = {**ret[to_merge], **ret.pop('fan_control')}
            except Exception as ex:
                pass

        if 'speaker' in ret and 'play_control' in ret:
            ret['speaker'] = {**ret['speaker'], **ret.pop('play_control')}

        if 'ambient_light' in ret and 'ambient_light_custom' in ret:
            ret['ambient_light'] = {**ret['ambient_light'], **ret.pop('ambient_light_custom')}

        if 'screen' in ret and 'indicator_light' not in ret:
            ret['indicator_light'] = ret.pop('screen')

        if 'humidifier' in ret and 'environment' in ret:
            # deerma.humidifier.mjjsq target_humidity misplaced
            if 'target_humidity' in ret['environment']:
                ret['humidifier']['target_humidity'] = (ret['environment'].pop('target_humidity'))

        if 'fan' in ret:
            if 'stepless_speed' in ret.get('custom_service', {}):
                ret['fan']['stepless_speed'] = (ret['custom_service'].pop('stepless_speed'))
            if 'stepless_speed' in ret.get('dm_service', {}):
                ret['fan']['stepless_speed'] = (ret['dm_service'].pop('stepless_speed'))

        # 把某个 service 里的 property 单独提出来
        # 例如：晾衣架的烘干，新风机的辅热
        if 'airer' in ret:
            if 'dryer' in ret['airer']:
                ret.setdefault('dryer', {})
                ret['dryer'].update({'switch_status': ret['airer'].pop('dryer')})
            if 'drying_level' in ret['airer']:
                ret.setdefault('dryer', {})
                ret['dryer'].update({'speed': ret['airer'].pop('drying_level')})

        if 'air_fresh' in ret:
            if 'heater' in ret['air_fresh']:
                ret.setdefault('air_fresh_heater', {})
                ret['air_fresh_heater'].update({'switch_status': ret['air_fresh'].pop('heater')})

        if not has_main:
            try:
                ret[list(ret.keys())[0]]['main'] = True
            except IndexError:
                pass

        for item in CUSTOM_SERVICES:
            ret.pop(item, None)
        return ret

    def get_all_actions(self):
        adict = {}
        for service in self.services.values():
            if a := self.get_action_by_siid(siid=service.siid):
                for k, v in a.items():
                    adict[f"{service.newid}_{k}"] = {
                        'siid': v.siid,
                        'aiid': v.aiid
                    }
        return adict


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