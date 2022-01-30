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
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice

from .basic_dev_class import (
    GenericMiotDevice,
    ToggleableMiotDevice,
    MiotSubDevice,
    MiotSubToggleableDevice,
    MiotIRDevice,
)
from . import async_generic_setup_platform
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
    await async_generic_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info,
        TYPE,
        {'default': MiotLight, '_ir_light': MiotIRLight},
        {'default': MiotSubLight}
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)


class MiotLight(ToggleableMiotDevice, LightEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._brightness = None
        self._color = None
        self._color_temp = None
        self._effect = None
        hass.async_add_job(self.create_sub_entities)

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
        parameters = []
        if 'switch_status' in self._ctrl_params:
            parameters.append({**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping[self._did_prefix + 'switch_status'])})
        elif 'brightness' in self._ctrl_params and ATTR_BRIGHTNESS not in kwargs:
            # for some devices that control onoff by setting brightness to 0
            parameters.append({**{'did': self._did_prefix + "brightness", 'value': self._ctrl_params['brightness']['value_range'][-2]}, **(self._mapping[self._did_prefix + 'brightness'])})
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

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        if 'switch_status' in self._ctrl_params:
            prm = self._ctrl_params['switch_status']['power_off']
            result = await self.set_property_new(self._did_prefix + "switch_status",prm)
        elif 'brightness' in self._ctrl_params:
            prm = self._ctrl_params['brightness']['value_range'][0]
            result = await self.set_property_new(self._did_prefix + "brightness",prm)
        else:
            raise NotImplementedError()
        if result:
            self._state = False
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
            return self.convert_value(self.extra_state_attributes[self._did_prefix + 'brightness'],"brightness",False,self._ctrl_params['brightness']['value_range'])
        except:
            return None

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        parameters = []
        if 'switch_status' in self._ctrl_params:
            parameters.append({**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])})
        elif 'brightness' in self._ctrl_params and ATTR_BRIGHTNESS not in kwargs:
            # for some devices that control onoff by setting brightness to 0
            parameters.append({**{'did': self._did_prefix + "brightness", 'value': self._ctrl_params['brightness']['value_range'][-2]}, **(self._mapping['brightness'])})
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

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        if 'switch_status' in self._ctrl_params:
            prm = self._ctrl_params['switch_status']['power_off']
            result = await self._parent_device.set_property_new(self._did_prefix + "switch_status",prm)
        elif 'brightness' in self._ctrl_params:
            prm = self._ctrl_params['brightness']['value_range'][0]
            result = await self._parent_device.set_property_new(self._did_prefix + "brightness",prm)
        else:
            raise NotImplementedError()
        if result:
            self._state = False
            # self._state_attrs[f"{self._did_prefix}switch_status"] = False
            self._parent_device.schedule_update_ha_state(force_refresh=True)
            self._skip_update = True

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        try:
            self._color_temp = self.convert_value(self.extra_state_attributes[self._did_prefix + 'color_temperature'], "color_temperature") or 100
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
            self._effect = self.get_key_by_value(self._ctrl_params['mode'],self.extra_state_attributes[self._did_prefix + 'mode'])
        except KeyError:
            self._effect = None
        return self._effect

    @property
    def hs_color(self):
        """Return the hs color value."""
        try:
            self._color = self.convert_value(self.extra_state_attributes[self._did_prefix + 'color'],"color",False)
        except KeyError:
            self._color = None
        return self._color

class MiotIRLight(MiotIRDevice, LightEntity):
    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        return 128

    @property
    def is_on(self):
        return self._state

    async def async_turn_on(self, **kwargs):
        result = False
        if ATTR_BRIGHTNESS in kwargs:
            if kwargs[ATTR_BRIGHTNESS] > 128:
                result = await self.async_send_ir_command('brightness_up')
            elif kwargs[ATTR_BRIGHTNESS] < 128:
                result = await self.async_send_ir_command('brightness_down')
            else:
                return
        else:
            result = await self.async_send_ir_command('turn_on')
        if result:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        result = await self.async_send_ir_command('turn_off')
        if result:
            self._state = False
            self.async_write_ha_state()
