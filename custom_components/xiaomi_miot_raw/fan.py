"""Platform for light integration."""
import asyncio
import logging
from functools import partial

from datetime import timedelta
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
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import GenericMiotDevice, ToggleableMiotDevice, MiotSubToggleableDevice
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
)
import copy

TYPE = 'fan'
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
    params = config.get(CONF_CONTROL_PARAMS)

    mappingnew = {}

    main_mi_type = None
    this_mi_type = []

    for t in MAP[TYPE]:
        if params.get(t):
            this_mi_type.append(t)
        if 'main' in (params.get(t) or ""):
            main_mi_type = t

    if main_mi_type:
        for k,v in mapping.items():
            for kk,vv in v.items():
                mappingnew[f"{k[:10]}_{kk}"] = vv

        _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])

        try:
            miio_device = MiotDevice(ip=host, token=token, mapping=mappingnew)
            device_info = miio_device.info()
            model = device_info.model
            _LOGGER.info(
                "%s %s %s detected",
                model,
                device_info.firmware_version,
                device_info.hardware_version,
            )

            device = MiotFan(miio_device, config, device_info, hass, main_mi_type)
        except DeviceException as de:
            _LOGGER.warn(de)
            raise PlatformNotReady

        hass.data[DATA_KEY][host] = device
        async_add_devices([device], update_before_add=True)
    else:
        _LOGGER.error("目前风扇只能作为主设备！")
        pass
    # TODO SUBFAN

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    # config[CONF_MAPPING] = config[CONF_MAPPING][TYPE]
    # config[CONF_CONTROL_PARAMS] = config[CONF_CONTROL_PARAMS][TYPE]
    await async_setup_platform(hass, config, async_add_entities)

class MiotFan(ToggleableMiotDevice, FanEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._speed = None
        self._oscillation = None

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if self._field_prefix + 'oscillate' in self._mapping:
            s |= SUPPORT_OSCILLATE
        if self._field_prefix + 'speed' in self._mapping:
            s |= SUPPORT_SET_SPEED
        return s

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return list(self._ctrl_params['speed'].keys())

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
        result = await self.set_property_new(self._field_prefix + "oscillate",self._ctrl_params['oscillate'][oscillating])

        if result:
            self._oscillation = True
            self._skip_update = True

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        parameters = [{**{'did': self._field_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]

        if speed:
            parameters.append({**{'did': self._field_prefix + "speed", 'value': self._ctrl_params['speed'][speed]}, **(self._mapping['speed'])})

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
        # self._speed = self._ctrl_params['speed'].get(self._state_attrs.get('speed_'))
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self._state_attrs.get(self._field_prefix + 'speed_'))
        except KeyError:
            pass
        self._oscillation = self._state_attrs.get(self._field_prefix + 'oscillate')
