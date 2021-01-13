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

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT cover"
DATA_KEY = "switch.xiaomi_miot_raw"
ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Required(CONF_MAPPING):vol.All(),
    vol.Required(CONF_CONTROL_PARAMS):vol.All(),
    
})


# pylint: disable=unused-argument

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
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

        device = MiotCover(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)
    
class MiotCover(GenericMiotDevice, CoverEntity):
    def __init__(self, device, config, device_info):
        GenericMiotDevice.__init__(self, device, config, device_info)
        self._current_position = 50
        self._target_position = 0
        self._action = 0

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
        return self._current_position == 0

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return False

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return False        
    
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['open'],
        )
        if result:
            self._skip_update = True
            
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['close'],

        )
        if result:
            self._skip_update = True
    async def async_stop_cover(self, **kwargs):
        """Close the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['stop'],
        )
        if result:
            self._skip_update = True

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
            
    async def async_update(self):
        # TODO
        """Fetch state from the device."""
        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False and self._skip_update:
            self._skip_update = False
            return
        
        try:
            response = await self.hass.async_add_job(partial(self.get_property, "current_position"))
            self._available = True

            statedict={}
            count4004 = 0
            for r in response:
                if r['code'] == 0:
                    try:
                        f = self._ctrl_params[r['did']]['value_ratio']
                        statedict[r['did']] = r['value'] * f
                    except KeyError:
                        statedict[r['did']] = r['value']
                else:
                    statedict[r['did']] = None
                    if r['code'] == -4004:
                        count4004 += 1
            if count4004 == len(response):
                self._assumed_state = True
                # _LOGGER.warn("设备不支持状态反馈")
                        

            self._state_attrs.update(statedict)


        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
        
        state = self._state_attrs['current_position']
        _LOGGER.debug("Got new state: %s", state)

        self._current_position = state

    
    def get_property(self, property_key: str):
        """Gets property value."""

        return self._device.send(
            "get_properties",
            [{"did": property_key, **self._device.mapping[property_key]}],
        )

