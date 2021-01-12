import asyncio
import logging
from functools import partial
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.entity import (
    Entity,
    ToggleEntity,
)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice
_LOGGER = logging.getLogger(__name__)

CONF_UPDATE_INSTANT = "update_instant"
CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'

ATTR_STATE_VALUE = "state_value"
ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

class GenericMiotDevice(Entity):
    """通用 MiOT 设备"""

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
        # self._icon = "mdi:flask-outline"

        self._available = None
        self._state = None
        self._assumed_state = False
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

    async def async_update(self):
        """Fetch state from the device."""
        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False and self._skip_update:
            self._skip_update = False
            return

        try:
            _props = [k for k in self._mapping]
            response = await self.hass.async_add_job(
                    self._device.get_properties_for_mapping
                )
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

class ToggleableMiotDevice(GenericMiotDevice, ToggleEntity):
    def __init__(self, device, config, device_info):
        GenericMiotDevice.__init__(self, device, config, device_info)
        
        
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

        await super().async_update()
        # if self._available:
        #     attrs = self._state_attrs
        #     self._state = attrs.get(self._attr) == 'on'
        state = self._state_attrs['switch_status']
        _LOGGER.debug("Got new state: %s", state)

        if state == self._ctrl_params['switch_status']['power_on']:
            self._state = True
        elif state == self._ctrl_params['switch_status']['power_off']:
            self._state = False
        elif not self.assumed_state:
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

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return self._assumed_state

    @property
    def state(self):
        return STATE_ON if self._state else STATE_OFF

    @property
    def is_on(self):
        return self._state

