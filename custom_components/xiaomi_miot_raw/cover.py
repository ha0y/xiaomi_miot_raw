import asyncio
import json
import logging
from datetime import timedelta
from functools import partial
from typing import Optional

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant.components.cover import (
    DEVICE_CLASS_CURTAIN, DOMAIN,
    ENTITY_ID_FORMAT, PLATFORM_SCHEMA,
    SUPPORT_CLOSE, SUPPORT_OPEN,
    SUPPORT_SET_POSITION, SUPPORT_STOP,
    CoverDevice, CoverEntity)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_TOKEN,
    SERVICE_CLOSE_COVER, SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER, SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER, SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE, SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED, STATE_CLOSING, STATE_OPEN,
    STATE_OPENING)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.util import Throttle
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import GenericMiotDevice
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

DEFAULT_NAME = "Generic MIoT cover"
DATA_KEY = "cover." + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
#     vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
#     vol.Required(CONF_HOST): cv.string,
#     vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
#     vol.Required(CONF_MAPPING):vol.All(),
#     vol.Required(CONF_CONTROL_PARAMS):vol.All(),
#     vol.Optional(CONF_CLOUD): vol.All(),
# }
    SCHEMA
)

SCAN_INTERVAL = timedelta(seconds=2)
# pylint: disable=unused-argument

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    
    _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])

    try:
        # miio_device = Device(host, token)
        miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        device = MiotCover(miio_device, config, device_info, hass)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)
   
async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)
 
class MiotCover(GenericMiotDevice, CoverEntity):
    def __init__(self, device, config, device_info, hass):
        GenericMiotDevice.__init__(self, device, config, device_info, hass)
        self._current_position = None
        self._target_position = None
        self._action = None
        # self._hass = hass
        # self._cloud = config.get(CONF_CLOUD)
        self._throttle1 = Throttle(timedelta(seconds=1))(self._async_update)
        self._throttle10 = Throttle(timedelta(seconds=10))(self._async_update)
        self.async_update = self._throttle10

    @property
    def available(self):
        """Return true when state is known."""
        return True
    
    @property
    def supported_features(self):
        if 'target_position' in self._mapping:
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        else:
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._current_position

    @property
    def is_closed(self):
        """Return if the cover is closed, same as position 0."""
        # try:
        return self._current_position == 0
        # except (ValueError, TypeError):
            # return None
    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        try:
            return self._action == self._ctrl_params['motor_status']['close']
        except KeyError:
            return None

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        try:
            return self._action == self._ctrl_params['motor_status']['open']
        except KeyError:
            return None

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        result = await self.set_property_new("motor_control",self._ctrl_params['motor_control']['open'])
        if result:
            # self._skip_update = True
            try:
                self._action = self._ctrl_params['motor_status']['open']
            except KeyError:
                return None

            self.async_update = self._throttle1
            
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        result = await self.set_property_new("motor_control",self._ctrl_params['motor_control']['close'])
        if result:
            try:
                self._action = self._ctrl_params['motor_status']['close']
            except KeyError:
                return None
            # self._skip_update = True
            self.async_update = self._throttle1

    async def async_stop_cover(self, **kwargs):
        """Close the cover."""
        result = await self.set_property_new("motor_control",self._ctrl_params['motor_control']['stop'])
        if result:
            # self._skip_update = True
            pass

    async def async_set_cover_position(self, **kwargs):
        """Set the cover."""
        result = await self.set_property_new("target_position",kwargs['position'])
        
        if result:
            self._skip_update = True
            
    async def _async_update(self):
        await super().async_update()
        self._current_position = self._state_attrs.get('current_position')
        self._action = self._state_attrs.get('motor_status')
        if self.is_closing or self.is_opening:
            self.async_update = self._throttle1
        else:
            self.async_update = self._throttle10
