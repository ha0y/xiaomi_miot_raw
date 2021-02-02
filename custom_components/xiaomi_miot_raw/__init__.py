import asyncio
import json
import logging
from datetime import timedelta
from functools import partial

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
from homeassistant.util import color
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

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
    SUPPORTED_DOMAINS,
)
# from .deps.xiaomi_cloud import *
# from .deps.xiaomi_cloud_alone import (
#     MiotCloud,
#     MiCloudException,
# )
from .deps.xiaomi_cloud_new import *
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
async def async_setup(hass, hassconfig):
    """Setup Component."""
    hass.data.setdefault(DOMAIN, {})

    config = hassconfig.get(DOMAIN) or {}
    hass.data[DOMAIN]['config'] = config
    hass.data[DOMAIN].setdefault('entities', {})
    hass.data[DOMAIN].setdefault('configs', {})

    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    hass.data[DOMAIN]['component'] = component

    await component.async_setup(config)
    return True

async def async_setup_entry(hass, entry):
    """Set up shopping list from config flow."""
    hass.data.setdefault(DOMAIN, {})

    config = {}
    for item in [CONF_NAME,
                 CONF_HOST,
                 CONF_TOKEN,
                 CONF_CLOUD,
                 'cloud_write',
                 'devtype',
                 ]:
        config[item] = entry.data.get(item)
    for item in [CONF_MAPPING,
                 CONF_CONTROL_PARAMS,
                 ]:
        config[item] = json.loads(entry.data.get(item))

    config['config_entry'] = entry
    entry_id = entry.entry_id
    unique_id = entry.unique_id
    hass.data[DOMAIN]['configs'][entry_id] = config
    hass.data[DOMAIN]['configs'][unique_id] = config

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, entry.data.get('devtype')))

    return True

class GenericMiotDevice(Entity):
    """通用 MiOT 设备"""

    def __init__(self, device, config, device_info, hass = None):
        """Initialize the entity."""
        self._device = device
        self._mapping = config.get(CONF_MAPPING)
        if type(self._mapping) == str:
            self._mapping = json.loads(self._mapping)

        self._ctrl_params = config.get(CONF_CONTROL_PARAMS)
        if type(self._ctrl_params) == str:
            self._mapping = json.loads(self._ctrl_params)

        self._name = config.get(CONF_NAME)
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False

        self._model = device_info.model
        self._unique_id = "{}-{}-{}".format(
            device_info.model, device_info.mac_address, self._name
        )
        # self._icon = "mdi:flask-outline"

        self._hass = hass
        self._cloud = config.get(CONF_CLOUD)
        self._cloud_write = config.get('cloud_write')
        self._cloud_instance = None
        if self._cloud:
            _LOGGER.info(f"Setting up xiaomi account for {self._name}...")
            mc = MiCloud(
                aiohttp_client.async_get_clientsession(self._hass)
            )
            mc.login_by_credientals(
                self._cloud.get('userId'),
                self._cloud.get('serviceToken'),
                self._cloud.get('ssecurity')
            )
            self._cloud_instance = mc


        self._available = None
        self._state = None
        self._assumed_state = False
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
            # ATTR_STATE_PROPERTY: self._state_property,
        }
        self._notified = False

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

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
            'manufacturer': (self._model or 'Xiaomi').split('.', 1)[0],
            'sw_version': self._state_attrs.get(ATTR_FIRMWARE_VERSION),
        }

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
                    p = {**{'did': did, 'value': params},**spiid}
                    p = {'params': [p]}
                    pp = json.dumps(p,separators=(',', ':'))
                    _LOGGER.info(f"Control {self._name} params: {pp}")
                    results = await self._cloud_instance.set_props(pp)
                    return True
                else:
                    did = self._cloud.get("did")
                    p = multiparams
                    for item in p:
                        item['did'] = did
                    pp = {'params': p}
                    ppp = json.dumps(pp,separators=(',', ':'))
                    _LOGGER.info(f"Control {self._name} params: {ppp}")
                    results = await self._cloud_instance.set_props(ppp)
                    return True


        except DeviceException as ex:
            _LOGGER.error('Set miot property to %s: %s(%s) failed: %s', self._name, field, params, ex)
            return False

    async def do_action_new(self, siid, aiid, params=None, did=None):
        params = {
            'did':  did or self.miot_did or f'action-{siid}-{aiid}',
            'siid': siid,
            'aiid': aiid,
            'in':   params or [],
        }

        try:
            if not self._cloud_write:
                result = await self._try_command(
                    f"Setting property for {self._name} failed.",
                    self._device.send,
                    "action",
                    params,
                )
                _LOGGER.error(result)
                if result:
                    return True
            else:
                result = await self._cloud_instance.do_action(
                    json.dumps({
                        'params': params or []
                    })
                )
                _LOGGER.error(result)
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
            return

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
                            f = self._ctrl_params[r['did']]['value_ratio']
                            statedict[r['did']] = round(r['value'] * f , 3)
                        except (KeyError, TypeError):
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
                            _LOGGER.error("Error getting %s 's property '%s' (code: %s)", self._name, r['did'], r['code'])
                if count4004 == len(response):
                    self._assumed_state = True
                    self._skip_update = True
                    # _LOGGER.warn("设备不支持状态反馈")
                    if not self._notified:
                        persistent_notification.async_create(
                            self._hass,
                            f"您添加的设备: **{self._name}** ，\n"
                            f"在获取 {count4004} 个状态时，\n"
                            f"全部返回 **-4004** 错误。\n"
                            "请考虑通过云端接入此设备来解决此问题。",
                            "设备可能不受支持")
                        self._notified = True

            else:
                _LOGGER.info(f"{self._name} is updating from cloud.")
                # with async_timeout.timeout(10):
                #     a = await self.async_update_from_mijia(
                #         aiohttp_client.async_get_clientsession(self._hass),
                #         # self._cloud.get("userId"),
                #         # self._cloud.get("serviceToken"),
                #         # self._cloud.get("ssecurity"),
                #         # self._cloud.get("did"),
                #     )
                data1 = {}
                data1['datasource'] = 1
                data1['params'] = []
                for value in self._mapping.values():
                    data1['params'].append({**{'did':self._cloud.get("did")},**value})
                data2 = json.dumps(data1,separators=(',', ':'))

                a = await self._cloud_instance.get_props(data2)

                dict1 = {}
                statedict = {}
                if a:
                    self._available = True
                    for item in a['result']:
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

            if statedict.get('brightness'):
                statedict['brightness_'] = statedict.pop('brightness')
            if statedict.get('speed'):
                statedict['speed_'] = statedict.pop('speed')
            if statedict.get('mode'):
                statedict['mode_'] = statedict.pop('mode')
            self._state_attrs.update(statedict)

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching %s 's state: %s", self._name, ex)

    def get_key_by_value(self, d:dict, value):
        try:
            return [k for k,v in d.items() if v == value][0]
        except (KeyError, ValueError, IndexError):
            _LOGGER.info(f"get_key_by_value: {value} is not in dict{json.dumps (d)}!")
            return None

    def convert_value(self, value, param, dir = True):
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
            valuerange = self._ctrl_params[param]['value_range']
            if dir:
                slider_value = round(value/255*100)
                return int(slider_value/100*(valuerange[1]-valuerange[0]+1)/valuerange[2])*valuerange[2]
            else:
                return round(value/(valuerange[1]-valuerange[0]+1)*255)
        elif param == 'target_humidity':
            valuerange = self._ctrl_params[param]['value_range']
            if value < valuerange[0]:
                return valuerange[0]
            elif value > valuerange[1]:
                return valuerange[1]
            else:
                return round((value - valuerange[0])/valuerange[2])*valuerange[2]+valuerange[0]

class ToggleableMiotDevice(GenericMiotDevice, ToggleEntity):
    def __init__(self, device, config, device_info, hass = None):
        GenericMiotDevice.__init__(self, device, config, device_info, hass)


    async def async_turn_on(self, **kwargs):
        """Turn on."""
        result = await self.set_property_new("switch_status",self._ctrl_params['switch_status']['power_on'])

        if result:
            self._state = True

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        result = await self.set_property_new("switch_status",self._ctrl_params['switch_status']['power_off'])

        if result:
            self._state = False

    async def async_update(self):

        await super().async_update()
        state = self._state_attrs.get('switch_status')
        _LOGGER.debug("%s 's new state: %s", self._name, state)

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

        self._state_attrs.update({ATTR_STATE_VALUE: state})

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

