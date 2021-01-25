from homeassistant.components.cover import (
    DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
    CoverEntity,
    DEVICE_CLASS_CURTAIN,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_TOKEN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import voluptuous as vol
import logging
from typing import Optional
from datetime import timedelta
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice
import asyncio
from functools import partial
from homeassistant.components.cover import PLATFORM_SCHEMA, CoverDevice
from homeassistant.exceptions import PlatformNotReady
from . import GenericMiotDevice
from aiohttp import ClientSession
import async_timeout
from homeassistant.helpers import aiohttp_client
from .deps.xiaomi_cloud import *
import json

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT cover"
DATA_KEY = "switch.xiaomi_miot_raw"
ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'
CONF_CLOUD = 'update_from_cloud'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Required(CONF_MAPPING):vol.All(),
    vol.Required(CONF_CONTROL_PARAMS):vol.All(),
    vol.Optional(CONF_CLOUD): vol.All(),
})

SCAN_INTERVAL = timedelta(seconds=1)
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
    # _LOGGER.info("正在初始化卷帘设备，位于 %s，token 开头为 %s...", host, token[:5])

    try:
        # miio_device = Device(host, token)
        miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            # "检测到 %s，固件: %s，硬件类型: %s",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        device = MiotCover(miio_device, config, device_info, hass)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)
    
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
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['open'],
        )
        if result:
            # self._skip_update = True
            try:
                self._action = self._ctrl_params['motor_status']['open']
            except KeyError:
                return None

            self.async_update = self._throttle1
            
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['close'],

        )
        if result:
            try:
                self._action = self._ctrl_params['motor_status']['close']
            except KeyError:
                return None
            # self._skip_update = True
            self.async_update = self._throttle1

    async def async_stop_cover(self, **kwargs):
        """Close the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['stop'],
        )
        if result:
            # self._skip_update = True
            pass

    async def async_set_cover_position(self, **kwargs):
        """Set the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "target_position",
            kwargs['position'],
        )
        if result:
            self._skip_update = True
            
    async def _async_update(self):
        await super().async_update()
        self._current_position = self._state_attrs['current_position']
        self._action = self._state_attrs.get('motor_status')
        if self.is_closing or self.is_opening:
            self.async_update = self._throttle1
        else:
            self.async_update = self._throttle10
