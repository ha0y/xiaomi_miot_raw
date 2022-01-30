import asyncio
import logging
from functools import partial

from datetime import timedelta
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
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

TYPE = 'binary_sensor'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

CONF_SENSOR_TYPE = "sensor_type"

SCAN_INTERVAL = timedelta(seconds=10)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)
DEVCLASS_MAPPING = {
    "door"     : ["contact_state"],
    "moisture" : ["submersion_state"],
    "motion"   : ["motion_state"],
}

# pylint: disable=unused-argument
@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    hass.data[DOMAIN]['add_handler'].setdefault(TYPE, {})
    if 'config_entry' in config:
        id = config['config_entry'].entry_id
        hass.data[DOMAIN]['add_handler'][TYPE].setdefault(id, async_add_devices)

    await async_generic_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info,
        TYPE,
        {'default': None},
        {'default': MiotSubBinarySensor}
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

"""因为目前二元传感器只作为传感器的子实体，所以不写主实体"""

class MiotSubBinarySensor(MiotSubDevice, BinarySensorEntity):
    def __init__(self, parent_device, mapping, params, mitype, others={}):
        super().__init__(parent_device, mapping, params, mitype)
        self._sensor_property = others.get('sensor_property')
        self.entity_id = f"{DOMAIN}.{parent_device._entity_id}-{others.get('sensor_property').split('_')[-1]}"

    @property
    def state(self):
        """Return the state of the device."""
        if self.is_on == True:
            return STATE_ON
        elif self.is_on == False:
            return STATE_OFF
        else:
            return STATE_UNKNOWN

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        try:
            return self._parent_device.extra_state_attributes[self._sensor_property]
        except:
            return None


    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._parent_device.unique_id)},
        }

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        try:
            return next(k for k,v in DEVCLASS_MAPPING.items() for item in v if item in self._sensor_property)
        except StopIteration:
            return None

    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._parent_device.unique_id}-{self._sensor_property}"

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return f"{self._parent_device.name} {self._sensor_property.replace('_', ' ').capitalize()}"

