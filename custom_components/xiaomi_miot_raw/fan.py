"""Platform for light integration."""
import asyncio
import logging
from functools import partial
import homeassistant.helpers.config_validation as cv
from homeassistant.util import color
import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice
from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_SPEED,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    PLATFORM_SCHEMA,
    FanEntity,
)
from . import ToggleableMiotDevice, GenericMiotDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT fan"
DATA_KEY = "fan.xiaomi_miot_raw"

CONF_UPDATE_INSTANT = "update_instant"
CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'

ATTR_STATE_VALUE = "state_value"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UPDATE_INSTANT, default=True): cv.boolean,
        
        vol.Required(CONF_MAPPING):vol.All(),
        vol.Required(CONF_CONTROL_PARAMS):vol.All(),

    }
)

ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

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

        device = MiotFan(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)
        
class MiotFan(ToggleableMiotDevice, FanEntity):
    def __init__(self, device, config, device_info):
        ToggleableMiotDevice.__init__(self, device, config, device_info)
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
        result = await self._try_command(
            "Turning the miio device off failed.",
            self._device.set_property,
            "oscillate",
            # self._ctrl_params['speed'][speed],
            self._ctrl_params['oscillate'][oscillating],
        )

        if result:
            self._oscillation = True
            self._skip_update = True
    
    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        parameters = [{**{'did': "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]
        
        if speed:
            parameters.append({**{'did': "speed", 'value': list(self._ctrl_params['speed'].keys())[list(self._ctrl_params['speed'].values()).index(speed)]}, **(self._mapping['speed'])}) 

        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.send,
            "set_properties",
            parameters,
        )
        if result:
            self._state = True
            self._skip_update = True
            
    async def async_update(self):
        await super().async_update()
        self._speed = self._ctrl_params['speed'].get(self._state_attrs.get('speed_'))
        self._oscillation = self._state_attrs.get('oscillate')
