"""Platform for light integration."""
import asyncio
import logging
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_SPEED, 
    PLATFORM_SCHEMA,
    SPEED_HIGH, 
    SPEED_LOW, 
    SPEED_MEDIUM,
    SPEED_OFF, 
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED, 
    FanEntity)
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
    SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT fan"
DATA_KEY = "fan." + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    # {
    #     vol.Required(CONF_HOST): cv.string,
    #     vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    #     vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    #     vol.Optional(CONF_UPDATE_INSTANT, default=True): cv.boolean,
    #     vol.Optional(CONF_CLOUD): vol.All(),
        
    #     vol.Required(CONF_MAPPING):vol.All(),
    #     vol.Required(CONF_CONTROL_PARAMS):vol.All(),

    # }
    SCHEMA
)

# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the fan from config."""

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

        device = MiotFan(miio_device, config, device_info, hass)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)
        
async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

class MiotFan(ToggleableMiotDevice, FanEntity):
    def __init__(self, device, config, device_info, hass):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass)
        self._speed = None
        self._oscillation = None
        
    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if 'oscillate' in self._mapping:
            s |= SUPPORT_OSCILLATE
        if 'speed' in self._mapping:
            s |= SUPPORT_SET_SPEED
        return s

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return list(self._ctrl_params['speed'].values())
    
    @property
    def speed(self):
        """Return the current speed."""
        return self._speed
    
    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillation

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        result = await self.set_property_new("oscillate",self._ctrl_params['oscillate'][oscillating])

        if result:
            self._oscillation = True
            self._skip_update = True
    
    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        parameters = [{**{'did': "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]
        
        if speed:
            parameters.append({**{'did': "speed", 'value': list(self._ctrl_params['speed'].keys())[list(self._ctrl_params['speed'].values()).index(speed)]}, **(self._mapping['speed'])}) 

        # result = await self._try_command(
        #     "Turning the miio device on failed.",
        #     self._device.send,
        #     "set_properties",
        #     parameters,
        # )
        result = await self.set_property_new(multiparams = parameters)
        if result:
            self._state = True
            self._skip_update = True
            
    async def async_update(self):
        await super().async_update()
        self._speed = self._ctrl_params['speed'].get(self._state_attrs.get('speed_'))
        self._oscillation = self._state_attrs.get('oscillate')
