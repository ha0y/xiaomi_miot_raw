"""Platform for light integration."""
import asyncio
import logging
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP,
    ATTR_EFFECT, ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP, SUPPORT_EFFECT,
    LightEntity)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import GenericMiotDevice, ToggleableMiotDevice
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
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT light"
DATA_KEY = "light." + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UPDATE_INSTANT, default=True): cv.boolean,
        vol.Optional(CONF_CLOUD): vol.All(),
        
        vol.Required(CONF_MAPPING):vol.All(),
        vol.Required(CONF_CONTROL_PARAMS):vol.All(),

    }
)

# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the light from config."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)

    _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])

    try:
        miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        device = MiotLight(miio_device, config, device_info, hass)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

      
class MiotLight(ToggleableMiotDevice, LightEntity):
    def __init__(self, device, config, device_info, hass):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass)
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
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    def convert_value(self, value, param, dir = True):
        if param == 'color':
            if dir:
                rgb = color.color_hs_to_RGB(*value)
                int_ = rgb[0] | rgb[1] << 8 | rgb[2] << 16
                return int_
            else:
                rgb = [0xFF & value, (0xFF00 & value) >> 8, (0xFF0000 & value) >> 16]
                hs = color.color_RGB_to_hs(*rgb)
                return hs
        else:
            valuerange = self._ctrl_params[param]['value_range']
            if dir:
                slider_value = round(value/255*100)
                return int(slider_value/100*(valuerange[1]-valuerange[0]+1)/valuerange[2])*valuerange[2]
            else:
                return round(value/(valuerange[1]-valuerange[0]+1)*255)

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        parameters = [{**{'did': "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]
        if ATTR_EFFECT in kwargs:
            modes = self._ctrl_params['mode']
            parameters.append({**{'did': "mode", 'value': list(modes.keys())[list(modes.values()).index(kwargs[ATTR_EFFECT])]}, **(self._mapping['mode'])}) 
        else:
            if ATTR_BRIGHTNESS in kwargs:
                self._effect = None
                parameters.append({**{'did': "brightness", 'value': self.convert_value(kwargs[ATTR_BRIGHTNESS],"brightness")}, **(self._mapping['brightness'])})
            if ATTR_COLOR_TEMP in kwargs:
                self._effect = None
                valuerange = self._ctrl_params['color_temperature']['value_range']
                ct = color.color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
                ct = valuerange[0] if ct < valuerange[0] else valuerange[1] if ct > valuerange[1] else ct
                parameters.append({**{'did': "color_temperature", 'value': ct}, **(self._mapping['color_temperature'])})
            if ATTR_HS_COLOR in kwargs:
                self._effect = None
                intcolor = self.convert_value(kwargs[ATTR_HS_COLOR],'color')
                parameters.append({**{'did': "color", 'value': intcolor}, **(self._mapping['color'])})
                

        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.send,
            "set_properties",
            parameters,
        )

        if result:
            self._state = True
            # self._skip_update = True
            
    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        try:
            return color.color_temperature_kelvin_to_mired(self._ctrl_params['color_temperature']['value_range'][1])
        except KeyError:
            return None
    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        try:
            return color.color_temperature_kelvin_to_mired(self._ctrl_params['color_temperature']['value_range'][0])
        except KeyError:
            return None
    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return list(self._ctrl_params['mode'].values()) #+ ['none']

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect
    
    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._color
    
    async def async_update(self):
        """Fetch state from the device."""
        # On state change some devices doesn't provide the new state immediately.
        await super().async_update()
        try:
            self._brightness = self.convert_value(self._state_attrs['brightness_'],"brightness",False)
        except KeyError: pass
        try:
            self._color = self.convert_value(self._state_attrs['color'],"color",False)
        except KeyError: pass
        try:
            self._color_temp = color.color_temperature_kelvin_to_mired(self._state_attrs['color_temperature'])
        except KeyError: pass
        try:
            self._state_attrs.update({'color_temperature': self._state_attrs['color_temperature']})
        except KeyError: pass
        try:
            self._state_attrs.update({'effect': self._state_attrs['mode']})
        except KeyError: pass
        try:
            self._effect = self._ctrl_params['mode'][self._state_attrs['mode']]
        except KeyError: 
            self._effect = None
