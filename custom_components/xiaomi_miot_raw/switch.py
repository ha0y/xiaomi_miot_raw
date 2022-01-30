import asyncio
import logging
from functools import partial

from datetime import timedelta
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
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

TYPE = 'switch'

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

    await async_generic_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info,
        TYPE,
        {'default': MiotSwitch},
        {'default': MiotSubSwitch}
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotSwitch(ToggleableMiotDevice, SwitchEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)


class MiotSubSwitch(MiotSubToggleableDevice, SwitchEntity):
    pass

class BinarySelectorEntity(MiotSubToggleableDevice, SwitchEntity):
    def __init__(self, parent_device, **kwargs):
        self._parent_device = parent_device
        self._did_prefix = f"{kwargs.get('did_prefix')[:10]}_" if kwargs.get('did_prefix') else ""
        self._field = kwargs.get('field')
        # self._value_list = kwargs.get('value_list')
        self._name_suffix = kwargs.get('name') or self._field.replace("_", " ").title()
        self._name = f'{parent_device.name} {self._name_suffix}'
        self._unique_id = f"{parent_device.unique_id}-{kwargs.get('field')}"
        self._entity_id = f"{parent_device._entity_id}-{kwargs.get('field')}"
        self.entity_id = f"{DOMAIN}.{self._entity_id}"
        self._available = True
        self._icon = "mdi:tune-variant"

    async def async_turn_on(self) -> None:
        result = await self._parent_device.set_property_new(self._did_prefix + self._field, True)
        if result:
            self._state = STATE_ON
            self.schedule_update_ha_state()

    async def async_turn_off(self) -> None:
        result = await self._parent_device.set_property_new(self._did_prefix + self._field, False)
        if result:
            self._state = STATE_OFF
            self.schedule_update_ha_state()

    @property
    def is_on(self):
        return self._parent_device.extra_state_attributes.get(self._did_prefix + self._field)

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {}
