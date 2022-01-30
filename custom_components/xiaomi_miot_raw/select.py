import asyncio
import logging
from functools import partial

from collections import OrderedDict
from datetime import timedelta
from homeassistant.const import __version__ as current_version
from distutils.version import StrictVersion
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import fan
from homeassistant.components.select import (
    PLATFORM_SCHEMA,
    SelectEntity
)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color
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

TYPE = 'select'
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
        {'default': MiotPropertySelector, 'a_l': MiotActionListNew}
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotPropertySelector(SelectEntity, MiotSubDevice):
    def __init__(self, parent_device, **kwargs):
        self._parent_device = parent_device
        self._full_did = kwargs.get('full_did')
        self._value_list = kwargs.get('value_list')
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
    def options(self):
        """Return a set of selectable options."""
        return list(self._value_list.keys())

    @property
    def current_option(self):
        """Return the selected entity option to represent the entity state."""
        return self._parent_device.extra_state_attributes[self._full_did]

    async def async_select_option(self, option: str):
        """Change the selected option."""
        result = await self._parent_device.set_property_new(self._full_did, self._value_list[option])
        if result:
            self._state_attrs[self._full_did] = option
            self.schedule_update_ha_state()

class MiotActionListNew(SelectEntity, MiotSubDevice):
    def __init__(self, parent_device, mapping, params, mitype):
        """params is not needed. We keep it here to make the ctor same."""
        super().__init__(parent_device, mapping, {}, mitype)
        self._name_suffix = '动作列表'
        self._action_list = []
        for k, v in mapping.items():
            if 'aiid' in v:
                self._action_list.append(k)

    @property
    def options(self):
        """Return a set of selectable options."""
        return self._action_list

    @property
    def current_option(self):
        """Return the selected entity option to represent the entity state."""
        return None

    async def async_select_option(self, option: str):
        """Change the selected option."""
        result = await self._parent_device.call_action_new(*self._mapping[option].values())
        if result:
            self._state = None
            self.schedule_update_ha_state()
