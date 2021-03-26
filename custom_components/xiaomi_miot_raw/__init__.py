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
    MAP,
    DUMMY_IP,
    DUMMY_TOKEN,
)

from .deps.xiaomi_cloud_new import *
from .deps.xiaomi_cloud_new import MiCloud
from .deps.miot_coordinator import MiotCloudCoordinator
from asyncio.exceptions import CancelledError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_TOKEN): cv.string,
                vol.Required(CONF_MAPPING): vol.All(),
                vol.Required(CONF_CONTROL_PARAMS): vol.All(),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SHORT_DELAY = 3
LONG_DELAY = 5
NOTIFY_INTERVAL = 60 * 10

OFFLINE_NOTIFY = False
UPDATE_BETA_FLAG = False

async def async_setup(hass, hassconfig):
    """Setup Component."""
    hass.data.setdefault(DOMAIN, {})

    config = hassconfig.get(DOMAIN) or {}
    hass.data[DOMAIN]['config'] = config
    hass.data[DOMAIN].setdefault('entities', {})
    hass.data[DOMAIN].setdefault('configs', {})
    hass.data[DOMAIN].setdefault('miot_main_entity', {})
    hass.data[DOMAIN].setdefault('micloud_devices', [])
    hass.data[DOMAIN].setdefault('cloud_instance_list', [])

    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    hass.data[DOMAIN]['component'] = component

    await component.async_setup(config)
    return True

async def async_setup_entry(hass, entry):
    """Set up shopping list from config flow."""
    hass.data.setdefault(DOMAIN, {})

    # entry for MiCloud login
    if 'username' in entry.data:
        return await _setup_micloud_entry(hass, entry)

    config = {}
    for item in [CONF_NAME,
                 CONF_HOST,
                 CONF_TOKEN,
                 CONF_CLOUD,
                 'cloud_write',
                 'devtype',
                 'ett_id_migrated',
                 'cloud_device_info',
                 ]:
        config[item] = entry.data.get(item)
    for item in [CONF_MAPPING,
                 CONF_CONTROL_PARAMS,
                 ]:
        config[item] = json.loads(entry.data.get(item))

    if type(entry.data.get('devtype')) == str:
        persistent_notification.async_create(
                            hass,
                            f"感谢您选择本插件！\n"
                            f"本插件最近的更新，支持了“一个设备多个类型”的配置方式，\n"
                            f"您的 **{entry.data.get(CONF_NAME)}** 配置项是旧版本格式。\n"
                            f"建议您重新添加设备，确认设备正常后删除旧设备，\n"
                            f"即可消除此提示。\n",
                            "Xiaomi MIoT")
        config[CONF_MAPPING] = {entry.data.get('devtype'): config[CONF_MAPPING]}
        config[CONF_CONTROL_PARAMS] = {entry.data.get('devtype'): config[CONF_CONTROL_PARAMS]}

    config['config_entry'] = entry
    entry_id = entry.entry_id
    unique_id = entry.unique_id
    hass.data[DOMAIN]['configs'][entry_id] = config
    hass.data[DOMAIN]['configs'][unique_id] = config

    if type(entry.data.get('devtype')) == str:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, entry.data.get('devtype')))
    else:
        for t in entry.data.get('devtype'):
            hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, t))

    return True

async def async_unload_entry(hass, entry):
    if 'username' in entry.data:
        # TODO
        try:
            hass.data[DOMAIN]['micloud_devices'] = []
            for item in hass.data[DOMAIN]['cloud_instance_list']:
                if item['username'] == entry.data['username']:
                    del item
                    return True
            return False
        except Exception as ex:
            _LOGGER.error(ex)
            return False
    else:
        entry_id = entry.entry_id
        unique_id = entry.unique_id
        hass.data[DOMAIN]['configs'].pop(entry_id)
        if unique_id:
            hass.data[DOMAIN]['configs'].pop(unique_id)
        if type(entry.data.get('devtype')) == str:
            hass.async_create_task(hass.config_entries.async_forward_entry_unload(entry, entry.data.get('devtype')))
        else:
            for t in entry.data.get('devtype'):
                hass.async_create_task(hass.config_entries.async_forward_entry_unload(entry, t))

        return True

async def _setup_micloud_entry(hass, config_entry):
    """Thanks to @AlexxIT """
    data: dict = config_entry.data.copy()
    server_location = data.get('server_location') or 'cn'

    session = aiohttp_client.async_create_clientsession(hass)
    cloud = MiCloud(session)
    cloud.svr = server_location

    if 'service_token' in data:
        # load devices with saved MiCloud auth
        cloud.auth = data
        devices = await cloud.get_total_devices([server_location])
    else:
        devices = None

    if devices is None:
        _LOGGER.debug(f"Login to MiCloud for {config_entry.title}")
        if await cloud.login(data['username'], data['password']):
            # update MiCloud auth in .storage
            data.update(cloud.auth)
            hass.config_entries.async_update_entry(config_entry, data=data)

            devices = await cloud.get_total_devices([server_location])

            if devices is None:
                _LOGGER.error("Can't load devices from MiCloud")

        else:
            _LOGGER.error("Can't login to MiCloud")
    if userid := cloud.auth.get('user_id'):
        # TODO don't allow login the same account twice
        hass.data[DOMAIN]['cloud_instance_list'].append({
            "user_id": userid,
            "username": data['username'],
            "cloud_instance": cloud,
            "coordinator": MiotCloudCoordinator(hass, cloud)
        })

    # load devices from or save to .storage
    filename = sanitize_filename(data['username'])
    store = Store(hass, 1, f"{DOMAIN}/{filename}.json")
    if devices is None:
        _LOGGER.debug("Loading a list of devices from the .storage")
        devices = await store.async_load()
    else:
        _LOGGER.debug(f"Loaded from MiCloud {len(devices)} devices")
        await store.async_save(devices)

    if devices is None:
        _LOGGER.debug("No devices in .storage")
        return False

    # TODO: Think about a bunch of devices
    if 'micloud_devices' not in hass.data[DOMAIN]:
        hass.data[DOMAIN]['micloud_devices'] = devices
    else:
        hass.data[DOMAIN]['micloud_devices'] += devices

    return True

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
                    aiohttp_client.async_get_clientsession(self._hass)
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

        if type(self._ctrl_params) == str:
            self._ctrl_params = json.loads(self._ctrl_params)

        if not type(self._ctrl_params) == OrderedDict:
            paramsnew = {}
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
        self._cloud = config.get(CONF_CLOUD)
        self._cloud_write = config.get('cloud_write')
        self._cloud_instance = None
        self.coordinator = None
        if self._cloud:
            c = setup_cloud(self, hass)
            self._cloud_instance = c[0]
            self.coordinator = c[1]
            self.coordinator.add_fixed_by_mapping(self._cloud, self._mapping)

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
        self._callbacks = set()

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
    def device_state_attributes(self):
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
            if result[0]['code'] == 0:
                return True
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

    async def call_action_new(self, siid, aiid, params2=None, did=None):
        params = {
            'did':  did or self._cloud.get("did") or f'action-{siid}-{aiid}',
            'siid': siid,
            'aiid': aiid,
            'in':   params2 or [],
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

    async def async_update(self):
        """Fetch state from the device."""
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
                        self._device.get_properties_for_mapping
                    )
                self._available = True

                statedict={}
                count4004 = 0
                for r in response:
                    if r['code'] == 0:
                        try:
                            f = self._ctrl_params_new[r['did']]['value_ratio']
                            statedict[r['did']] = round(r['value'] * f , 3)
                        except (KeyError, TypeError, IndexError):
                            if (('status' in r['did'] and 'switch_status' not in r['did']) \
                                or 'fault' in r['did']) \
                                and type(r['value']) == int:
                                if r['did'] in self._ctrl_params_new:
                                    if s := self.get_key_by_value(self._ctrl_params_new[r['did']], r['value']):
                                        statedict[r['did']] = s
                                        continue
                            statedict[r['did']] = r['value']
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
                        if r['code'] == -4004:
                            count4004 += 1
                        else:
                            _LOGGER.info("Error getting %s 's property '%s' (code: %s)", self._name, r['did'], r['code'])
                if count4004 == len(response):
                    self._assumed_state = True
                    self._skip_update = True
                    # _LOGGER.warn("设备不支持状态反馈")
                    if time.time() - self._last_notified > NOTIFY_INTERVAL:
                        persistent_notification.async_create(
                            self._hass,
                            f"您添加的设备: **{self._name}** ，\n"
                            f"在获取 {count4004} 个状态时，\n"
                            f"全部返回 **-4004** 错误。\n"
                            "请考虑通过云端接入此设备来解决此问题。",
                            "设备可能不受支持")
                        self._last_notified = time.time()

            else:
                _LOGGER.info(f"{self._name} is updating from cloud.")
                data1 = {}
                data1['datasource'] = 1
                data1['params'] = []
                for value in self._mapping.values():
                    if 'aiid' not in value:
                        data1['params'].append({**{'did':self._cloud.get("did")},**value})
                data2 = json.dumps(data1,separators=(',', ':'))

                a = await self._cloud_instance.get_props(data2, self._cloud.get("server_location"))

                dict1 = {}
                statedict = {}
                if a:
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
                        dict1.setdefault(item['siid'], {})
                        dict1[item['siid']][item['piid']] = item.get('value')

                    for key, value in self._mapping.items():
                        try:
                            if (('status' in key and 'switch_status' not in key) \
                                or 'fault' in key) \
                                and type(dict1[value['siid']][value['piid']]) == int:
                                if key in self._ctrl_params_new:
                                    if s := self.get_key_by_value(self._ctrl_params_new[key], dict1[value['siid']][value['piid']]):
                                        statedict[key] = s
                                        continue
                            statedict[key] = dict1[value['siid']][value['piid']]
                        except KeyError:
                            statedict[key] = None

                else:
                    pass

            self._fail_count = 0
            self._state_attrs.update(statedict)
            self._handle_platform_specific_attrs()
            self.publish_updates()

        except DeviceException as ex:
            if self._fail_count < 3:
                self._fail_count += 1
                self._available = False
                _LOGGER.info("Got exception while fetching %s 's state: %s. Count %d", self._name, ex, self._fail_count)
            else:
                self._available = False
                _LOGGER.error("Got exception while fetching %s 's state: %s", self._name, ex)

    def get_key_by_value(self, d:dict, value):
        try:
            return [k for k,v in d.items() if v == value][0]
        except (KeyError, ValueError, IndexError):
            _LOGGER.info(f"get_key_by_value: {value} is not in dict{json.dumps (d)}!")
            return None

    def convert_value(self, value, param, dir = True, valuerange = None):
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
                _LOGGER.warning(
                    "New state (%s) of %s doesn't match expected values: %s/%s",
                    state, self._name,
                    self._ctrl_params['switch_status']['power_on'],
                    self._ctrl_params['switch_status']['power_off'],
                )
                self._state = None
        else:
            self._state = None

        self._state_attrs.update({ATTR_STATE_VALUE: state})
        # await self.publish_updates()


class MiotSubDevice(Entity):
    """This part is modified from @al-one 's."""
    # should_poll = False
    def __init__(self, parent_device, mapping, params, mitype):
        self._unique_id = f'{parent_device.unique_id}-{mitype}'
        self._entity_id = f"{parent_device._entity_id}-{mitype}"
        self.entity_id = f"{DOMAIN}.{self._entity_id}"
        self._name = f'{parent_device.name} {mitype.replace("_", " ").title()}'
        self._state = STATE_UNKNOWN
        self._available = True
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
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def available(self):
        return self._available

    @property
    def device_state_attributes(self):
        try:
            return self._parent_device.device_state_attributes or {}
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
        attrs = self._parent_device.device_state_attributes or {}
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
            return STATE_ON if self.device_state_attributes.get(f"{self._did_prefix}switch_status") else STATE_OFF
        except:
            return STATE_UNKNOWN

def sanitize_filename(s: str):
    valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ','_')
    return filename

@dataclass
class dev_info:
    model             : str
    mac_address       : str     # Not available for cloud
    firmware_version  : str
    hardware_version  : str     # Not available for cloud


async def async_generic_setup_platform(
    hass,
    config,
    async_add_devices,
    discovery_info,
    TYPE,           # 每个设备类型调用此函数时指定自己的类型，因此函数执行中只处理这个类型的设备
    main_class_dict : dict,
    sub_class_dict : dict = {},
    *,
    special_dict={}
):
    DATA_KEY = TYPE + '.' + DOMAIN
    hass.data.setdefault(DATA_KEY, {})

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)

    mappingnew = {}

    main_mi_type = None
    other_mi_type = []

    for t in MAP[TYPE]:
        if mapping.get(t):
            other_mi_type.append(t)
        if 'main' in (params.get(t) or ""):
            main_mi_type = t

    try:
        other_mi_type.remove(main_mi_type)
    except:
        pass

    if main_mi_type or type(params) == OrderedDict:
        for k,v in mapping.items():
            for kk,vv in v.items():
                mappingnew[f"{k[:10]}_{kk}"] = vv

        _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])
        if type(params) == OrderedDict:
            miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        else:
            miio_device = MiotDevice(ip=host, token=token, mapping=mappingnew)
        try:
            if host == DUMMY_IP and token == DUMMY_TOKEN:
                raise DeviceException
            device_info = miio_device.info()
            model = device_info.model
            _LOGGER.info(
                "%s %s %s detected",
                model,
                device_info.firmware_version,
                device_info.hardware_version,
            )
        except DeviceException as de:
            if not config.get(CONF_CLOUD):
                _LOGGER.warn(de)
                raise PlatformNotReady
            else:
                if not (di := config.get('cloud_device_info')):
                    _LOGGER.error(f"未能获取到设备信息，请删除 {config.get(CONF_NAME)} 重新配置。")
                    raise PlatformNotReady
                else:
                    device_info = dev_info(
                        di['model'],
                        di['mac'],
                        di['fw_version'],
                        ""
                    )
        if main_mi_type in main_class_dict:
            device = main_class_dict[main_mi_type](miio_device, config, device_info, hass, main_mi_type)
        else:
            device = main_class_dict['default'](miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)

    elif not sub_class_dict:
        _LOGGER.error(f"{TYPE}只能作为主设备！请检查{config.get(CONF_NAME)}配置")

    if sub_class_dict:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(f'{host}-{config.get(CONF_NAME)}'):
                break
            else:
                retry_time *= 2
                if retry_time > 30:
                    _LOGGER.error(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after 30 seconds!")
                    raise PlatformNotReady
                else:
                    _LOGGER.debug(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after {retry_time - 1} seconds.")
                    await asyncio.sleep(retry_time)

        for k,v in mapping.items():
            if k in MAP[TYPE]:
                for kk,vv in v.items():
                    mappingnew[f"{k[:10]}_{kk}"] = vv

        devices = []

        for item in other_mi_type:
            if item == "indicator_light":
                if not params[item].get('enabled'):
                    continue

            if item in sub_class_dict:
                devices.append(sub_class_dict[item](parent_device, mapping.get(item), params.get(item), item))
            else:
                devices.append(sub_class_dict['default'](parent_device, mapping.get(item), params.get(item), item))

        async_add_devices(devices, update_before_add=True)
