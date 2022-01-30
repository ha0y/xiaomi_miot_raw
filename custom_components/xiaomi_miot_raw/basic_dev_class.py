import asyncio
import json
import time
import logging
from datetime import timedelta
from functools import partial
from dataclasses import dataclass

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant.const import *
from homeassistant.core import callback
from homeassistant.components import persistent_notification
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client, discovery
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.util import color
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice
import copy
import math
from collections import OrderedDict

from .deps.const import (
    DOMAIN,
    CONF_UPDATE_INSTANT,
    CONF_MAPPING,
    CONF_CONTROL_PARAMS,
    CONF_CLOUD,
    CONF_MODEL,
    ATTR_STATE_VALUE,
    ATTR_MODEL,
    ATTR_FIRMWARE_VERSION,
    ATTR_HARDWARE_VERSION,
    SCHEMA,
    SERVICE_SCHEMA,
    SERVICE_TO_METHOD,
    MAP,
    DUMMY_IP,
    DUMMY_TOKEN,
)

from .deps.xiaomi_cloud_new import *
from .deps.xiaomi_cloud_new import MiCloud
from .deps.miot_coordinator import MiotCloudCoordinator
from asyncio.exceptions import CancelledError
from . import (HAVE_NUMBER, HAVE_SELECT)


_LOGGER = logging.getLogger(__name__)

SHORT_DELAY = 3
LONG_DELAY = 5
NOTIFY_INTERVAL = 60 * 10

OFFLINE_NOTIFY = False
UPDATE_BETA_FLAG = False

class GenericMiotDevice(Entity):
    """通用 MiOT 设备"""

    def __init__(self, device, config, device_info, hass = None, mi_type = None):
        """Initialize the entity."""

        def setup_cloud(self, hass) -> tuple:
            try:
                return next((cloud['cloud_instance'], cloud['coordinator']) for cloud in hass.data[DOMAIN]['cloud_instance_list']
                            if cloud['user_id'] == self._cloud.get('userId'))
            except StopIteration:
                _LOGGER.info(f"Setting up xiaomi account for {self._name}...")
                mc = MiCloud(
                    aiohttp_client.async_create_clientsession(self._hass, auto_cleanup=False)
                )
                mc.login_by_credientals(
                    self._cloud.get('userId'),
                    self._cloud.get('serviceToken'),
                    self._cloud.get('ssecurity')
                )
                co = MiotCloudCoordinator(hass, mc)
                hass.data[DOMAIN]['cloud_instance_list'].append({
                    "user_id": self._cloud.get('userId'),
                    "username": None,  # 不是从UI配置的用户，没有用户名
                    "cloud_instance": mc,
                    "coordinator": co
                })
                return (mc, co)

        self._device = device
        self._mi_type = mi_type
        self._did_prefix = f"{self._mi_type[:10]}_" if self._mi_type else ""

        self._mapping = config.get(CONF_MAPPING)
        if type(self._mapping) == str:
            # 旧版单设备配置格式
            self._mapping = json.loads(self._mapping)
        elif type(self._mapping) == OrderedDict:
            # YAML 配置格式
            pass
        else:
            mappingnew = {}
            for k,v in self._mapping.items():
                for kk,vv in v.items():
                    mappingnew[f"{k[:10]}_{kk}"] = vv
            self._mapping = mappingnew

        self._ctrl_params = config.get(CONF_CONTROL_PARAMS) or {}
        self._max_properties = 10

        if type(self._ctrl_params) == str:
            self._ctrl_params = json.loads(self._ctrl_params)

        if not type(self._ctrl_params) == OrderedDict:
            paramsnew = {}
            self._max_properties = self._ctrl_params.pop('max_properties', 10)
            for k,v in self._ctrl_params.items():
                for kk,vv in v.items():
                    paramsnew[f"{k[:10]}_{kk}"] = vv
            self._ctrl_params_new = paramsnew
        else:
            self._ctrl_params_new = self._ctrl_params

        if mi_type:
            self._ctrl_params = self._ctrl_params[mi_type]

        self._name = config.get(CONF_NAME)
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False
        self._delay_update = 0

        self._model = device_info.model
        self._unique_id = "{}-{}-{}".format(
            device_info.model, device_info.mac_address, self._name
        ) if not config.get('ett_id_migrated') else (
            f"{device_info.model.split('.')[-1]}-cloud-{config.get(CONF_CLOUD)['did'][-6:]}" if config.get(CONF_CLOUD) else
                f"{device_info.model.split('.')[-1]}-{device_info.mac_address.replace(':','')}"
        )
        if config.get('ett_id_migrated'):
            self._entity_id = self._unique_id
            self.entity_id = f"{DOMAIN}.{self._entity_id}"
        else:
            self._entity_id = None

        self._hass = hass
        self._entry_id = config['config_entry'].entry_id if 'config_entry' in config else None
        self._cloud = config.get(CONF_CLOUD)
        self._cloud_write = config.get('cloud_write')
        self._cloud_instance = None
        self.coordinator = None
        self._body_for_update_cloud = None
        if self._cloud:
            c = setup_cloud(self, hass)
            self._cloud_instance = c[0]
            self.coordinator = c[1]
            self.coordinator.add_fixed_by_mapping(self._cloud, self._mapping)

            data1 = {}
            data1['datasource'] = 1
            data1['params'] = []
            for value in self._mapping.values():
                if 'aiid' not in value:
                    data1['params'].append({**{'did':self._cloud.get("did")},**value})
            self._body_for_update_cloud = json.dumps(data1,separators=(',', ':'))

        self._fail_count = 0
        self._available = None
        self._state = None
        self._assumed_state = False
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
        }
        self._last_notified = 0
        self._err4004_notified = False
        self._callbacks = set()

        for service in (SERVICE_TO_METHOD):
            schema = SERVICE_TO_METHOD[service].get("schema", SERVICE_SCHEMA)
            hass.services.async_register(
                DOMAIN, service, self.async_service_handler, schema=schema
            )

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True if (not UPDATE_BETA_FLAG or not self._cloud) else False

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    # @property
    # def icon(self):
    #     """Return the icon to use for device if any."""
    #     return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._unique_id)},
            'name': self._name,
            'model': self._model,
            'manufacturer': (self._model or 'Xiaomi').split('.', 1)[0].capitalize(),
            'sw_version': self._state_attrs.get(ATTR_FIRMWARE_VERSION),
        }

    @property
    def did_prefix(self):
        return self._did_prefix

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_job(partial(func, *args, **kwargs))

            _LOGGER.info("Response received from %s: %s", self._name, result)
            # This is a workaround. The action should not only return whether operation succeed, but also the 'out'.
            if 'aiid' in result:
                return True if result['code'] == 0 else False
            return True if result[0]['code'] == 0 else False

        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def set_property_new(self, field = "", params = "", multiparams:list = []):
        try:
            if not self._cloud_write:
                if not multiparams:
                    result = await self._try_command(
                        f"Setting property for {self._name} failed.",
                        self._device.set_property,
                        field,
                        params,
                    )
                    if result:
                        if field in self._state_attrs:
                            self._state_attrs[field] = params
                        return True
                else:
                    result = await self._try_command(
                        f"Setting property for {self._name} failed.",
                        self._device.send,
                        "set_properties",
                        multiparams,
                    )
                    if result:
                        return True
                return False
            else:
                _LOGGER.info(f"Control {self._name} by cloud.")
                if not multiparams:
                    did = self._cloud.get("did")
                    spiid = self._mapping.get(field) or {}
                    if not (spiid := self._mapping.get(field)):
                        _LOGGER.error(f"Cannot control {self._name} by cloud because can't find {field} siid and piid from {self._mapping}")
                        return False
                    p = {**{'did': did, 'value': params},**spiid}
                    p = {'params': [p]}
                    pp = json.dumps(p,separators=(',', ':'))
                    _LOGGER.info(f"Control {self._name} params: {pp}")
                    results = await self._cloud_instance.set_props(pp, self._cloud.get("server_location"))
                    if results:
                        if r := results.get('result'):
                            for item in r:
                                if item['code'] == 1:
                                    self._delay_update = LONG_DELAY
                                elif item['code'] == -704042011:
                                    if self._available == True or self._available == None:
                                        if OFFLINE_NOTIFY:
                                            persistent_notification.async_create(
                                                self._hass,
                                                f"请注意，云端接入设备 **{self._name}** 已离线。",
                                                "Xiaomi MIoT - 设备离线")
                                        else:
                                            _LOGGER.warn(f"请注意，云端接入设备 **{self._name}** 已离线。")
                                    self._available = False
                                    self._skip_update = True
                                    return False
                                elif item['code'] != 0:
                                    _LOGGER.error(f"Control {self._name} by cloud failed: {r}")
                                    return False
                            if field in self._state_attrs:
                                self._state_attrs[field] = params
                            self._skip_update = True
                            return True
                    return False
                else:
                    did = self._cloud.get("did")
                    p = multiparams
                    for item in p:
                        item['did'] = did
                    pp = {'params': p}
                    ppp = json.dumps(pp,separators=(',', ':'))
                    _LOGGER.info(f"Control {self._name} params: {ppp}")
                    results = await self._cloud_instance.set_props(ppp, self._cloud.get("server_location"))
                    if results:
                        if r := results.get('result'):
                            for item in r:
                                if item['code'] == 1:
                                    self._delay_update = LONG_DELAY
                                elif item['code'] == -704042011:
                                    if self._available == True or self._available == None:
                                        if OFFLINE_NOTIFY:
                                            persistent_notification.async_create(
                                                self._hass,
                                                f"请注意，云端接入设备 **{self._name}** 已离线。",
                                                "Xiaomi MIoT - 设备离线")
                                        else:
                                            _LOGGER.warn(f"请注意，云端接入设备 **{self._name}** 已离线。")
                                    self._available = False
                                    self._skip_update = True
                                    return False
                                elif item['code'] != 0:
                                    _LOGGER.error(f"Control {self._name} by cloud failed: {r}")
                                    return False
                            self._skip_update = True
                            return True
                    return False

        except DeviceException as ex:
            _LOGGER.error('Set miot property to %s: %s(%s) failed: %s', self._name, field, params, ex)
            return False

    async def call_action_new(self, siid, aiid, inn=None, did=None):
        if did is not None:
            did_ = did
        elif self._cloud is not None:
            did_ = self._cloud.get("did")
        else:
            did_ = f'action-{siid}-{aiid}'
        params = {
            'did':  did_,
            'siid': siid,
            'aiid': aiid,
            'in':   inn or [],
        }

        try:
            if not self._cloud_write:
                result = await self._try_command(
                    f"Calling action for {self._name} failed.",
                    self._device.send,
                    "action",
                    params,
                )
                if result:
                    return True
            else:
                result = await self._cloud_instance.call_action(
                    json.dumps({
                        'params': params or []
                    }), self._cloud.get("server_location")
                )
                if result:
                    return True
        except DeviceException as ex:
            _LOGGER.error('Call miot action to %s (%s) failed: %s', self._name, params, ex)
            return False

    async def set_property_for_service(self, siid, piid, value):
        try:
            if not self._cloud_write:
                result = await self._try_command(
                    f"Setting property for {self._name} failed.",
                    self._device.send,
                    "set_properties",
                    [{"did": f"set-{siid}-{piid}", "siid": siid, "piid": piid, "value": value}],
                )
            else:
                did = self._cloud.get("did")
                p = {'params': [{"did": did, "siid": siid, "piid": piid, "value": value}]}
                pp = json.dumps(p,separators=(',', ':'))
                results = await self._cloud_instance.set_props(pp, self._cloud.get("server_location"))
        except DeviceException as ex:
            _LOGGER.error('Set miot property to %s failed: %s', self._name, ex)

    async def async_update(self):
        """Fetch state from the device."""
        def pre_process_data(key, value):
            if value is None:
                return None
            try:
                if key in self._ctrl_params_new:
                    if f := self._ctrl_params_new[key].get('value_ratio'):
                        return round(value * f , 3)
                    if 'value_list' in self._ctrl_params_new[key]:
                        if s := self.get_key_by_value(self._ctrl_params_new[key]['value_list'], value):
                            return s
                    elif (('status' in key and 'switch_status' not in key) \
                        or 'state' in key \
                        or 'fault' in key) \
                        and type(value) == int:
                        if s := self.get_key_by_value(self._ctrl_params_new[key], value):
                            return s
                return value
            except KeyError:
                return None

        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False or self._skip_update:
            self._skip_update = False
            self._delay_update = 0
            return
        if self._delay_update != 0:
            await asyncio.sleep(self._delay_update)
            self._delay_update = 0
        try:
            if not self._cloud:
                response = await self.hass.async_add_job(
                    partial(self._device.get_properties_for_mapping, max_properties=self._max_properties)
                )
                self._available = True

                statedict={}
                props_with_4004 = []
                for r in response:
                    if r['code'] == 0:
                        statedict[r['did']] = pre_process_data(r['did'], r['value'])
                    elif r['code'] == 9999:
                        persistent_notification.async_create(
                            self._hass,
                            f"您添加的设备: **{self._name}** ，\n"
                            f"在获取个状态时，\n"
                            f"返回 **-9999** 错误。\n"
                            "请考虑通过云端接入此设备来解决此问题。",
                            "设备不支持本地接入")
                    else:
                        statedict[r['did']] = None
                        if r['code'] == -4004 and not self._err4004_notified:
                            props_with_4004.append(r['did'])
                        else:
                            _LOGGER.info("Error getting %s 's property '%s' (code: %s)", self._name, r['did'], r['code'])
                if not self._err4004_notified:
                    if len(props_with_4004) == len(response):
                        self._assumed_state = True
                        self._skip_update = True
                        # _LOGGER.warn("设备不支持状态反馈")
                        if not self._err4004_notified:
                            persistent_notification.async_create(
                                self._hass,
                                f"您添加的设备: **{self._name}** ，\n"
                                f"在获取 {len(response)} 个状态时，\n"
                                f"全部返回 **-4004** 错误。\n"
                                "请考虑通过云端接入此设备来解决此问题。",
                                "设备可能不受支持")
                            self._err4004_notified = True
                            del props_with_4004
                    elif len(props_with_4004) != 0:
                        _LOGGER.warn(f"Device {self._name} returns unknown error for property {props_with_4004}. If you encounter issues about this device, try enabling Cloud Access.")
                        self._err4004_notified = True
                        del props_with_4004

            else:
                _LOGGER.info(f"{self._name} is updating from cloud.")

                a = await self._cloud_instance.get_props(self._body_for_update_cloud, self._cloud.get("server_location"))

                dict1 = {}
                statedict = {}
                if a:
                    if a['code'] != 0:
                        _LOGGER.error(f"Error updating {self._name} from cloud: {a}")
                        return None
                    if all(item['code'] == -704042011 for item in a['result']):
                        if self._available == True or self._available == None:
                            if OFFLINE_NOTIFY:
                                persistent_notification.async_create(
                                    self._hass,
                                    f"请注意，云端接入设备 **{self._name}** 已离线。",
                                    "Xiaomi MIoT - 设备离线")
                            else:
                                _LOGGER.warn(f"请注意，云端接入设备 **{self._name}** 已离线。")
                        self._available = False
                    else:
                        self._available = True

                    for item in a['result']:
                        # TODO handle -704030013 (Unreadable property)
                        dict1.setdefault(item['siid'], {})
                        dict1[item['siid']][item['piid']] = item.get('value')

                    for key, value in self._mapping.items():
                        if 'aiid' in value:
                            continue
                        statedict[key] = pre_process_data(key, dict1[value['siid']][value['piid']])

                else:
                    pass

            self._fail_count = 0
            self._state_attrs.update(statedict)
            self._handle_platform_specific_attrs()
            self.publish_updates()

        except (DeviceException, OSError) as ex:
            if self._fail_count < 3:
                self._fail_count += 1
                _LOGGER.info("Got exception while fetching %s 's state: %s. Count %d", self._name, ex, self._fail_count)
            else:
                self._available = False
                _LOGGER.error("Got exception while fetching %s 's state: %s", self._name, ex)

    async def create_sub_entities(self):
        """这里应该用_ctrl_params_new，因为已经包含所有子设备，所以运行一次附加到主设备即可，不重不漏
        此处设置好添加条件后，到sensor处排除掉这些实体。"""
        if not self._ctrl_params_new:
            return
        if HAVE_NUMBER:
            from .number import MiotNumberInput
        if HAVE_SELECT:
            from .select import MiotPropertySelector
        num_to_add = []
        sel_to_add = []
        for k,v in self._ctrl_params_new.items():
            if not isinstance(v, dict):
                continue
            if 'access' in v and 'value_range' in v and HAVE_NUMBER:
                if v['access'] >> 1 & 0b01:
                    num_to_add.append(MiotNumberInput(
                        self,
                        full_did=k,
                        value_range=v['value_range']
                    ))
            elif 'access' in v and 'value_list' in v and HAVE_SELECT:
                if v['access'] >> 1 & 0b01:
                    sel_to_add.append(MiotPropertySelector(
                        self,
                        full_did=k,
                        value_list=v['value_list']
                    ))

        if num_to_add:
            self._hass.data[DOMAIN]['add_handler']['number'][self._entry_id](num_to_add, update_before_add=True)
        if sel_to_add:
            self._hass.data[DOMAIN]['add_handler']['select'][self._entry_id](sel_to_add, update_before_add=True)



    def get_key_by_value(self, d:dict, value):
        try:
            return [k for k,v in d.items() if v == value][0]
        except (KeyError, ValueError, IndexError):
            _LOGGER.info(f"get_key_by_value: {value} is not in dict{json.dumps (d)}!")
            return None

    def convert_value(self, value, param, dir = True, valuerange = None):
        if value is None:
            return None
        if not type(value) == int and not type(value) == float and not type(value) == tuple:
            _LOGGER.debug(f"Converting {param} value ({value}) is not a number but {type(value)}, trying to convert to number")
            try:
                value = float(value)
            except Exception as ex:
                _LOGGER.error(f"Error converting value, type:{param}, value:{value}({type(value)}), error:{ex}")
                return None
        try:
            if param == 'color':
                if dir:
                    rgb = color.color_hs_to_RGB(*value)
                    int_ =  rgb[0] << 16 | rgb[1] << 8 | rgb[2]
                    return int_
                else:
                    rgb = [(0xFF0000 & value) >> 16, (0xFF00 & value) >> 8, 0xFF & value]
                    hs = color.color_RGB_to_hs(*rgb)
                    return hs
            elif param == 'brightness':
                # valuerange = self._ctrl_params[param]['value_range']
                if dir:
                    slider_value = round(value/255*100)
                    return int(slider_value/100*(valuerange[1]-valuerange[0]+1)/valuerange[2])*valuerange[2]
                else:
                    return round(value/(valuerange[1]-valuerange[0]+1)*255)
            elif param == 'current_position':
                if dir:
                    return int((value/100*(valuerange[1]-valuerange[0])+valuerange[0])/valuerange[2])*valuerange[2]
                else:
                    return round((value-valuerange[0])/(valuerange[1]-valuerange[0])*100)
            elif param == 'target_humidity':
                # valuerange = self._ctrl_params[param]['value_range']
                if value < valuerange[0]:
                    return valuerange[0]
                elif value > valuerange[1]:
                    return valuerange[1]
                else:
                    return round((value - valuerange[0])/valuerange[2])*valuerange[2]+valuerange[0]
            elif param == 'volume':
                if dir:
                    value *= valuerange[1]
                    return round((value - valuerange[0])/valuerange[2])*valuerange[2]+valuerange[0]
                else:
                    return value / valuerange[1]
            elif param == 'color_temperature':
                # dir: mired to kelvin; not dir: kelvin to mired
                # both are 1000000 / value
                # if value != 0:
                return math.floor(1000000 / value)
                # else:
        except Exception as ex:
            _LOGGER.error(f"Error converting value, type:{param}, value:{value}, error:{ex}")
            return None

    def register_callback(self, callback):
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        if UPDATE_BETA_FLAG and self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        dict1 = {}
        statedict = {}
        if self._cloud['did'] in self.coordinator.data:
            if all(item['code'] == -704042011 for item in self.coordinator.data[self._cloud['did']]):
                if self._available == True or self._available == None:
                    if OFFLINE_NOTIFY:
                        persistent_notification.async_create(
                            self._hass,
                            f"请注意，云端接入设备 **{self._name}** 已离线。",
                            "Xiaomi MIoT - 设备离线")
                    else:
                        _LOGGER.warn(f"请注意，云端接入设备 **{self._name}** 已离线。")
                self._available = False
            else:
                self._available = True
            for item in self.coordinator.data[self._cloud['did']]:
                if dict1.get(item['siid']):
                    dict1[item['siid']][item['piid']] = item.get('value')
                else:
                    dict1[item['siid']] = {}
                    dict1[item['siid']][item['piid']] = item.get('value')

            for key, value in self._mapping.items():
                try:
                    statedict[key] = dict1[value['siid']][value['piid']]
                except KeyError:
                    statedict[key] = None
        else:
            pass

        self._state_attrs.update(statedict)
        self._handle_platform_specific_attrs()
        self.async_write_ha_state()
        self.publish_updates()

    def _handle_platform_specific_attrs(self):
        pass

    @asyncio.coroutine
    def async_service_handler(self, service):
        """Map services to methods on XiaomiMiioDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [
                device
                for device in self.hass.data[DOMAIN]['entities'].values()
                if device.entity_id in entity_ids
            ]
        else:
            # devices = hass.data[DOMAIN]['entities'].values()
            devices = []
            _LOGGER.error("No entity_id specified.")

        update_tasks = []
        for device in devices:
            yield from getattr(device, method["method"])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=self.hass.loop)

class ToggleableMiotDevice(GenericMiotDevice, ToggleEntity):
    def __init__(self, device, config, device_info, hass = None, mi_type = None):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, mi_type)

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        prm = self._ctrl_params['switch_status']['power_on']
        result = await self.set_property_new(self._did_prefix + "switch_status",prm)
        if result:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        prm = self._ctrl_params['switch_status']['power_off']
        result = await self.set_property_new(self._did_prefix + "switch_status",prm)
        if result:
            self._state = False
            self.async_write_ha_state()

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return self._assumed_state

    @property
    def state(self):
        return STATE_ON if self._state else STATE_OFF

    @property
    def is_on(self):
        return self._state

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        state = self._state_attrs.get(self._did_prefix + 'switch_status')
        _LOGGER.debug("%s 's new state: %s", self._name, state)
        if 'switch_status' in self._ctrl_params:
            if state == self._ctrl_params['switch_status']['power_on']:
                self._state = True
            elif state == self._ctrl_params['switch_status']['power_off']:
                self._state = False
            elif not self.assumed_state:
                self._state = None
        else:
            self._state = None

        self._state_attrs.update({ATTR_STATE_VALUE: state})
        # await self.publish_updates()

class MiotSubDevice(Entity):
    def __init__(self, parent_device, mapping, params, mitype):
        self._unique_id = f'{parent_device.unique_id}-{mitype}'
        self._entity_id = f"{parent_device._entity_id}-{mitype}"
        self.entity_id = f"{DOMAIN}.{self._entity_id}"
        self._name_suffix = mitype.replace("_", " ").title()
        if mitype in params:
            if params[mitype].get('name'):
                self._name_suffix = params[mitype]['name']
        self._state = STATE_UNKNOWN
        self._icon = None
        self._parent_device = parent_device
        self._state_attrs = {}
        self._mapping = mapping
        self._ctrl_params = params
        self._mitype = mitype
        self._did_prefix= f"{mitype[:10]}_" if mitype else ""
        self._skip_update = False

        self.convert_value = parent_device.convert_value
        self.get_key_by_value = parent_device.get_key_by_value

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        return f'{self._parent_device.name} {self._name_suffix}'

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        return self._parent_device.available

    @property
    def extra_state_attributes(self):
        try:
            return self._parent_device.extra_state_attributes or {}
        except:
            return None

    @property
    def device_info(self):
        return self._parent_device.device_info

    async def async_added_to_hass(self):
        self._parent_device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self._parent_device.remove_callback(self.async_write_ha_state)

    # @property
    # def unit_of_measurement(self):
    #     return self._option.get('unit')

    async def async_update(self):
        if self._skip_update:
            self._skip_update = False
            return
        attrs = self._parent_device.extra_state_attributes or {}
        self._state_attrs = attrs
        pass

class MiotSubToggleableDevice(MiotSubDevice):
    async def async_turn_on(self, **kwargs):
        """Turn on."""
        prm = self._ctrl_params['switch_status']['power_on']
        result = await self._parent_device.set_property_new(self._did_prefix + "switch_status",prm)
        if result:
            self._state = True
            self._state_attrs[f"{self._did_prefix}switch_status"] = True
            self._parent_device.schedule_update_ha_state(force_refresh=True)
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        prm = self._ctrl_params['switch_status']['power_off']
        result = await self._parent_device.set_property_new(self._did_prefix + "switch_status",prm)
        if result:
            self._state = False
            self._state_attrs[f"{self._did_prefix}switch_status"] = False
            self._parent_device.schedule_update_ha_state(force_refresh=True)
            self._skip_update = True

    @property
    def is_on(self):
        return STATE_ON if self.state else STATE_OFF

    @property
    def available(self):
        return True

    @property
    def state(self):
        try:
            return STATE_ON if self.extra_state_attributes.get(f"{self._did_prefix}switch_status") else STATE_OFF
        except:
            return STATE_UNKNOWN

class MiotIRDevice(GenericMiotDevice):
    def __init__(self, config, hass, did_prefix):
        def setup_cloud(self, hass) -> tuple:
            try:
                return next((cloud['cloud_instance'], cloud['coordinator']) for cloud in hass.data[DOMAIN]['cloud_instance_list']
                            if cloud['user_id'] == self._cloud.get('userId'))
            except StopIteration:
                _LOGGER.info(f"Setting up xiaomi account for {self._name}...")
                mc = MiCloud(
                    aiohttp_client.async_create_clientsession(self._hass, auto_cleanup=False)
                )
                mc.login_by_credientals(
                    self._cloud.get('userId'),
                    self._cloud.get('serviceToken'),
                    self._cloud.get('ssecurity')
                )
                co = MiotCloudCoordinator(hass, mc)
                hass.data[DOMAIN]['cloud_instance_list'].append({
                    "user_id": self._cloud.get('userId'),
                    "username": None,  # 不是从UI配置的用户，没有用户名
                    "cloud_instance": mc,
                    "coordinator": co
                })
                return (mc, co)

        self._mapping = config.get(CONF_MAPPING)
        if type(self._mapping) == str:
            # 旧版单设备配置格式
            self._mapping = json.loads(self._mapping)
        elif type(self._mapping) == OrderedDict:
            # YAML 配置格式
            pass
        else:
            mappingnew = {}
            for k,v in self._mapping.items():
                for kk,vv in v.items():
                    mappingnew[f"{k}_{kk}"] = vv
            self._mapping = mappingnew
        self._ctrl_params = config.get(CONF_CONTROL_PARAMS) or {}

        self._name = config.get(CONF_NAME)
        self._did_prefix = did_prefix + '_'
        self._update_instant = config.get(CONF_UPDATE_INSTANT)

        self._unique_id = f"miotir-cloud-{config.get(CONF_CLOUD)['did'][-6:]}"
        self._entity_id = self._unique_id
        self.entity_id = f"{DOMAIN}.{self._entity_id}"

        self._hass = hass
        self._entry_id = config['config_entry'].entry_id if 'config_entry' in config else None
        self._cloud = config.get(CONF_CLOUD)
        self._cloud_write = config.get('cloud_write')
        self._cloud_instance = None
        self.coordinator = None
        self._body_for_update_cloud = None
        if self._cloud:
            c = setup_cloud(self, hass)
            self._cloud_instance = c[0]
            self.coordinator = c[1]
            self.coordinator.add_fixed_by_mapping(self._cloud, self._mapping)

            data1 = {}
            data1['datasource'] = 1
            data1['params'] = []
            for value in self._mapping.values():
                if 'aiid' not in value:
                    data1['params'].append({**{'did':self._cloud.get("did")},**value})
            self._body_for_update_cloud = json.dumps(data1,separators=(',', ':'))

        self._state = None
        self._state_attrs = {}
        self._available = True

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def should_poll(self):
        """Poll the IR device."""
        return False

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._unique_id)},
            'name': self._name,
            'manufacturer': 'Xiaomi'
        }

    async def async_send_ir_command(self, command:str):
        if 'a_l_' + self._did_prefix + command not in self._mapping:
            _LOGGER.error(f'Failed to send IR command {command} to {self._name} because it cannot be found in mapping.')
            return False
        result = await self.call_action_new(*(self._mapping['a_l_' + self._did_prefix + command].values()))
        return True if result else False

    # async def async_update(self):
    #     pass