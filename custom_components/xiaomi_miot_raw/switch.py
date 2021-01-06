import asyncio
import logging
from functools import partial
import json
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DATA_KEY = "switch.xiaomi_miot_raw"

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
        
        vol.Optional(CONF_MAPPING):vol.All(),
        vol.Optional(CONF_CONTROL_PARAMS):vol.All(),

    }
)

ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

SUCCESS = ["ok"]


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
        miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        device = XiaomiMiioGenericDevice(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)


class XiaomiMiioGenericDevice(SwitchEntity):
    """通用 MiOT 开关"""

    def __init__(self, device, config, device_info):
        """Initialize the entity."""
        self._device = device
        self._mapping = config.get(CONF_MAPPING)
        self._ctrl_params = config.get(CONF_CONTROL_PARAMS)

        self._name = config.get(CONF_NAME)
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False

        self._model = device_info.model
        self._unique_id = "{}-{}-{}".format(
            device_info.model, device_info.mac_address, self._name
        )
        self._icon = "mdi:flask-outline"

        self._available = None
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
            # ATTR_STATE_PROPERTY: self._state_property,
        }

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
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

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

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "switch_status",
            self._ctrl_params['switch_status']['power_on'],
        )
        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        result = await self._try_command(
            "Turning the miio device off failed.",
            self._device.set_property,
            "switch_status",
            self._ctrl_params['switch_status']['power_off'],
        )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False and self._skip_update:
            self._skip_update = False
            return

        try:
            # _props = self._state_property.copy()[0]
            _props = [k for k in self._mapping]
            # _LOGGER.error(_props)
            # _LOGGER.error(type(_props))
            response = await self.hass.async_add_job(
                    self._device.get_properties_for_mapping
                )
            # state = await self.hass.async_add_job(
            #     self._device.send, self._state_property_getter, [_props]
            # )
            # state = str(state.pop()['value'])
            statedict={}
            for r in response:
                try:
                    statedict[r['did']] = r['value']
                except:
                    pass
            state = statedict['switch_status']
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            if state == self._ctrl_params['switch_status']['power_on']:
                self._state = True
            elif state == self._ctrl_params['switch_status']['power_off']:
                self._state = False
            else:
                _LOGGER.warning(
                    "New state (%s) doesn't match expected values: %s/%s",
                    state,
                    self._ctrl_params['switch_status']['power_on'],
                    self._ctrl_params['switch_status']['power_off'],
                )
                _LOGGER.warning(type(self._ctrl_params['switch_status']['power_on']))
                _LOGGER.warning(type(state))
                self._state = None

            self._state_attrs.update({ATTR_STATE_VALUE: state})

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
