"""Platform for light integration."""
import asyncio
import logging
from functools import partial

from datetime import timedelta
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP,
    ATTR_EFFECT, ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP, SUPPORT_EFFECT,
    LightEntity)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import GenericMiotDevice, ToggleableMiotDevice, MiotSubToggleableDevice, dev_info
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
import copy

TYPE = 'light'

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

# pylint: disable=unused-argument
@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the light from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

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
        device = MiotLight(miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    if other_mi_type:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(f'{host}-{config.get(CONF_NAME)}'):
                break
            else:
                retry_time *= 2
                if retry_time > 120:
                    _LOGGER.error(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after 120 seconds!")
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
            devices.append(MiotSubLight(parent_device, mapping.get(item), params.get(item), item))
        async_add_devices(devices, update_before_add=True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    # config[CONF_MAPPING] = config[CONF_MAPPING][TYPE]
    # config[CONF_CONTROL_PARAMS] = config[CONF_CONTROL_PARAMS][TYPE]
    await async_setup_platform(hass, config, async_add_entities)


class MiotLight(ToggleableMiotDevice, LightEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._brightness = None
        self._color = None
        self._color_temp = None
        self._effect = None

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if self._did_prefix + 'brightness' in self._mapping:
            s |= SUPPORT_BRIGHTNESS
        if self._did_prefix + 'color_temperature' in self._mapping:
            s |= SUPPORT_COLOR_TEMP
        if self._did_prefix + 'mode' in self._mapping:
            s |= SUPPORT_EFFECT
        if self._did_prefix + 'color' in self._mapping:
            s |= SUPPORT_COLOR
        return s

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        parameters = [{**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping[self._did_prefix + 'switch_status'])}]
        if ATTR_EFFECT in kwargs:
            modes = self._ctrl_params['mode']
            parameters.append({**{'did': self._did_prefix + "mode", 'value': self._ctrl_params['mode'].get(kwargs[ATTR_EFFECT])}, **(self._mapping[self._did_prefix + 'mode'])})
        if ATTR_BRIGHTNESS in kwargs:
            self._effect = None
            parameters.append({**{'did': self._did_prefix + "brightness", 'value': self.convert_value(kwargs[ATTR_BRIGHTNESS],"brightness", True, self._ctrl_params['brightness']['value_range'])}, **(self._mapping[self._did_prefix + 'brightness'])})
        if ATTR_COLOR_TEMP in kwargs:
            self._effect = None
            valuerange = self._ctrl_params['color_temperature']['value_range']
            ct = self.convert_value(kwargs[ATTR_COLOR_TEMP], "color_temperature")
            ct = valuerange[0] if ct < valuerange[0] else valuerange[1] if ct > valuerange[1] else ct
            parameters.append({**{'did': self._did_prefix + "color_temperature", 'value': ct}, **(self._mapping[self._did_prefix + 'color_temperature'])})
        if ATTR_HS_COLOR in kwargs:
            self._effect = None
            intcolor = self.convert_value(kwargs[ATTR_HS_COLOR],'color')
            parameters.append({**{'did': self._did_prefix + "color", 'value': intcolor}, **(self._mapping[self._did_prefix + 'color'])})

        result = await self.set_property_new(multiparams = parameters)

        if result:
            self._state = True
            self.async_write_ha_state()

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        try:
            return self.convert_value(self._ctrl_params['color_temperature']['value_range'][1], "color_temperature") or 1
        except KeyError:
            return None
    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        try:
            return self.convert_value(self._ctrl_params['color_temperature']['value_range'][0], "color_temperature") or 100
        except KeyError:
            return None
    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return list(self._ctrl_params['mode'].keys()) #+ ['none']

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._color

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        try:
            self._brightness = self.convert_value(self._state_attrs[self._did_prefix + 'brightness'],"brightness",False,self._ctrl_params['brightness']['value_range'])
        except KeyError: pass
        try:
            self._color = self.convert_value(self._state_attrs[self._did_prefix + 'color'],"color",False)
        except KeyError: pass
        try:
            self._color_temp = self.convert_value(self._state_attrs[self._did_prefix + 'color_temperature'], "color_temperature") or 100
        except KeyError: pass
        try:
            self._state_attrs.update({'color_temperature': self._state_attrs[self._did_prefix + 'color_temperature']})
        except KeyError: pass
        try:
            self._state_attrs.update({'mode': self._state_attrs['mode']})
        except KeyError: pass
        try:
            self._effect = self.get_key_by_value(self._ctrl_params['mode'],self._state_attrs[self._did_prefix + 'mode'])
        except KeyError:
            self._effect = None

class MiotSubLight(MiotSubToggleableDevice, LightEntity):
    def __init__(self, parent_device, mapping, params, mitype):
        super().__init__(parent_device, mapping, params, mitype)
        self._brightness = None
        self._color = None
        self._color_temp = None
        self._effect = None

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if 'brightness' in self._mapping:
            s |= SUPPORT_BRIGHTNESS
        if 'color_temperature' in self._mapping:
            s |= SUPPORT_COLOR_TEMP
        if 'mode' in self._mapping:
            s |= SUPPORT_EFFECT
        if 'color' in self._mapping:
            s |= SUPPORT_COLOR
        return s

    @property
    def brightness(self):
        """Return the brightness of the light."""
        try:
            return self.convert_value(self.device_state_attributes[self._did_prefix + 'brightness'],"brightness",False,self._ctrl_params['brightness']['value_range'])
        except:
            return None

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        parameters = [{**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]
        if ATTR_EFFECT in kwargs:
            modes = self._ctrl_params['mode']
            parameters.append({**{'did': self._did_prefix + "mode", 'value': self._ctrl_params['mode'].get(kwargs[ATTR_EFFECT])}, **(self._mapping['mode'])})
        if ATTR_BRIGHTNESS in kwargs:
            self._effect = None
            parameters.append({**{'did': self._did_prefix + "brightness", 'value': self.convert_value(kwargs[ATTR_BRIGHTNESS],"brightness", True, self._ctrl_params['brightness']['value_range'])}, **(self._mapping['brightness'])})
        if ATTR_COLOR_TEMP in kwargs:
            self._effect = None
            valuerange = self._ctrl_params['color_temperature']['value_range']
            ct = self.convert_value(kwargs[ATTR_COLOR_TEMP], "color_temperature")
            ct = valuerange[0] if ct < valuerange[0] else valuerange[1] if ct > valuerange[1] else ct
            parameters.append({**{'did': self._did_prefix + "color_temperature", 'value': ct}, **(self._mapping['color_temperature'])})
        if ATTR_HS_COLOR in kwargs:
            self._effect = None
            intcolor = self.convert_value(kwargs[ATTR_HS_COLOR],'color')
            parameters.append({**{'did': self._did_prefix + "color", 'value': intcolor}, **(self._mapping['color'])})

        result = await self._parent_device.set_property_new(multiparams = parameters)

        if result:
            self._state = True
            self._state_attrs[f"{self._did_prefix}switch_status"] = True
            self._parent_device.schedule_update_ha_state(force_refresh=True)

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        try:
            self._color_temp = self.convert_value(self.device_state_attributes[self._did_prefix + 'color_temperature'], "color_temperature") or 100
        except KeyError: pass
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        try:
            return self.convert_value(self._ctrl_params['color_temperature']['value_range'][1], "color_temperature") or 1
        except KeyError:
            return None
    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        try:
            return self.convert_value(self._ctrl_params['color_temperature']['value_range'][0], "color_temperature") or 100
        except KeyError:
            return None
    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return list(self._ctrl_params['mode'].keys()) #+ ['none']

    @property
    def effect(self):
        """Return the current effect."""
        try:
            self._effect = self.get_key_by_value(self._ctrl_params['mode'],self.device_state_attributes[self._did_prefix + 'mode'])
        except KeyError:
            self._effect = None
        return self._effect

    @property
    def hs_color(self):
        """Return the hs color value."""
        try:
            self._color = self.convert_value(self.device_state_attributes[self._did_prefix + 'color'],"color",False)
        except KeyError:
            self._color = None
        return self._color
