import asyncio
import logging
from functools import partial

from datetime import timedelta
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.number import PLATFORM_SCHEMA, NumberEntity
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice

from .basic_dev_class import (
    MiotSubDevice,
    MiotSubToggleableDevice
)
from . import async_generic_setup_platform
from .sensor import MiotSubSensor
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

TYPE = 'number'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN
SCAN_INTERVAL = timedelta(seconds=10)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)
# pylint: disable=unused-argument
@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    hass.data[DOMAIN]['add_handler'].setdefault(TYPE, {})
    if 'config_entry' in config:
        id = config['config_entry'].entry_id
        hass.data[DOMAIN]['add_handler'][TYPE].setdefault(id, async_add_devices)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotNumberInput(NumberEntity, MiotSubDevice):
    def __init__(self, parent_device, **kwargs):
        self._parent_device = parent_device
        self._full_did = kwargs.get('full_did')
        self._value_range = kwargs.get('value_range')
        self._name = f'{parent_device.name} {self._full_did}'
        self._unique_id = f"{parent_device.unique_id}-{kwargs.get('full_did')}"
        self._entity_id = f"{parent_device._entity_id}-{kwargs.get('full_did')}"
        self.entity_id = f"{DOMAIN}.{self._entity_id}"
        self._available = True
        self._skip_update = False
        self._icon = None

    @property
    def name(self):
        return f'{self._parent_device.name} {self._full_did.replace("_", " ").title()}'
    
    @property
    def state(self):
        """Return the state of the device."""
        try:
            return self._parent_device.extra_state_attributes[self._full_did]
        except:
            return None

    @property
    def value(self):
        if self.state is not None:
            try:
                return float(self.state)
            except Exception as ex:
                _LOGGER.error(ex)

    async def async_set_value(self, value):
        result = await self._parent_device.set_property_new(self._full_did, value)
        if result:
            self._state_attrs[self._full_did] = value
            self._parent_device.schedule_update_ha_state(force_refresh=True)
            self._skip_update = True

    @property
    def min_value(self):
        """Return the minimum value."""
        return self._value_range[0]

    @property
    def max_value(self):
        """Return the maximum value."""
        return self._value_range[1]

    @property
    def step(self):
        """Return the increment/decrement step."""
        return self._value_range[2]
