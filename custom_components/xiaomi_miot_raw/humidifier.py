import asyncio
import json
import logging
from datetime import timedelta
from functools import partial
from typing import Optional

from collections import OrderedDict
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant.components.humidifier import (
    HumidifierEntity, PLATFORM_SCHEMA)
from homeassistant.const import *
from homeassistant.components.humidifier.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.util import Throttle
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice

from .basic_dev_class import (
    GenericMiotDevice,
    ToggleableMiotDevice,
    MiotSubDevice,
    MiotSubToggleableDevice
)
from . import async_generic_setup_platform
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
    DUMMY_IP,
    DUMMY_TOKEN,
)
import copy
TYPE = 'humidifier'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

SCAN_INTERVAL = timedelta(seconds=10)
# pylint: disable=unused-argument

@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    await async_generic_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info,
        TYPE,
        {'default': MiotHumidifier},
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotHumidifier(ToggleableMiotDevice, HumidifierEntity):
    """Representation of a humidifier device."""
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._target_humidity = None
        self._mode = None
        self._available_modes = None
        self._device_class = DEVICE_CLASS_HUMIDIFIER

    @property
    def supported_features(self):
        """Return the list of supported features."""
        s = 0
        if self._did_prefix + 'mode' in self._mapping:
            s |= SUPPORT_MODES
        return s

    @property
    def min_humidity(self):
        try:
            return (self._ctrl_params['target_humidity']['value_range'][0])
        except KeyError:
            return None

    @property
    def max_humidity(self):
        try:
            return (self._ctrl_params['target_humidity']['value_range'][1])
        except KeyError:
            return None

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def mode(self):
        """Return current mode."""
        return self._mode

    @property
    def available_modes(self):
        """Return available modes."""
        return list(self._ctrl_params['mode'].keys())

    @property
    def device_class(self):
        """Return the device class of the humidifier."""
        return self._device_class

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        hum = self.convert_value(humidity, "target_humidity", True, self._ctrl_params['target_humidity']['value_range'])
        result = await self.set_property_new(self._did_prefix + "target_humidity", hum)
        if result:
            self._target_humidity = hum
            self.async_write_ha_state()

    async def async_set_mode(self, mode):
        """Update mode."""
        result = await self.set_property_new(self._did_prefix + "mode", self._ctrl_params['mode'].get(mode))

        if result:
            self._mode = mode
            self.async_write_ha_state()

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        self._target_humidity = self._state_attrs.get(self._did_prefix + 'target_humidity')
        self._mode = self.get_key_by_value(self._ctrl_params['mode'], self._state_attrs.get(self._did_prefix + 'mode'))
