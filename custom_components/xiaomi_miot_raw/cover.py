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
import json
from homeassistant.components.cover import PLATFORM_SCHEMA, CoverDevice
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DATA_KEY = "switch.xiaomi_miot_raw"
ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"
SUCCESS = ["ok"]

CONF_MODEL = 'model'
CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_MODEL): cv.string,
    vol.Optional(CONF_MAPPING):vol.All(),
    vol.Optional(CONF_CONTROL_PARAMS):vol.All(),
    
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

        device = XiaomiMiotGenericCover(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)

class XiaomiMiotGenericCover(CoverEntity):
    """Representation of a Xiaomi Miio Generic Device."""

    def __init__(self, device, config, device_info):
        """Initialize the entity."""
        self._device = device
        self._ctrl_params = config.get(CONF_CONTROL_PARAMS)
        self._mapping = config.get(CONF_MAPPING)
        self._name = config.get(CONF_NAME)
        # self._turn_on_command = config.get(CONF_TURN_ON_COMMAND)
        # self._turn_on_parameters = config.get(CONF_TURN_ON_PARAMETERS)
        # self._turn_off_command = config.get(CONF_TURN_OFF_COMMAND)
        # self._turn_off_parameters = config.get(CONF_TURN_OFF_PARAMETERS)
        # self._state_property = config.get(CONF_STATE_PROPERTY)
        # self._state_property_getter = config.get(CONF_STATE_PROPERTY_GETTER)
        # self._state_on_value = config.get(CONF_STATE_ON_VALUE)
        # self._state_off_value = config.get(CONF_STATE_OFF_VALUE)
        # self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False

        self._model = device_info.model
        # self._unique_id = "{}-{}-{}".format(
        #     device_info.model, device_info.mac_address, self._state_property
        # )
        self._unique_id = "{}-{}".format(
            device_info.model, device_info.mac_address
        )
        self._icon = "mdi:flask-outline"

        # self._available = None
        self._available = True
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
            # ATTR_STATE_PROPERTY: self._state_property,
            # "signal_strength": device_info.network_interface,
        }
        
        
        self._current_position = 50
        self._target_position = 0
        self._action = 0


    # @property
    # def should_poll(self):
    #     """Poll the miio device."""
    #     return True

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
    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_job(partial(func, *args, **kwargs))

            _LOGGER.info("Response received from miio device: %s", result)

            if result[0]['code'] == 0:
                return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    # These methods allow HA to tell the actual device what to do. In this case, move
    # the cover to the desired position, or open and close it all the way.
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "motor_control",
            self._ctrl_params['motor_control']['open'],
        )
        if result:
            # self._state = True
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
            # self._state = True
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
            # self._state = True
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
            # self._state = True
            self._skip_update = True
    # @property
    # def is_on(self):
    #     """Return true if switch is on."""
    #     return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

