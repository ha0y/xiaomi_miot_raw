""" This component doesn't support lock yet. This is for child lock! """
import asyncio
import logging
from functools import partial

from datetime import timedelta
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.lock import LockEntity, PLATFORM_SCHEMA
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

TYPE = 'lock'

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

# pylint: disable=unused-argument
@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the light from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)

    mappingnew = {}

    main_mi_type = None
    other_mi_type = []

    for t in MAP[TYPE]:
        if mapping.get(t):
            other_mi_type.append(t)
        if 'main' in (params.get(t) or ""):
            main_mi_type = t

    try:
        other_mi_type.remove(main_mi_type)
    except:
        pass

    if other_mi_type:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(config['config_entry'].entry_id):
                break
            else:
                retry_time *= 2
                if retry_time > 120:
                    _LOGGER.error(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after 120 seconds!")
                    raise PlatformNotReady
                else:
                    _LOGGER.debug(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after {retry_time - 1} seconds.")
                    await asyncio.sleep(retry_time)

        for k,v in mapping.items():
            if k in MAP[TYPE]:
                for kk,vv in v.items():
                    mappingnew[f"{k[:10]}_{kk}"] = vv

        devices = []

        for item in other_mi_type:
            if item == "physical_controls_locked":
                if params[item].get('enabled') == True:
                    devices.append(MiotPhysicalControlLock(parent_device, mapping.get(item), params.get(item), item))
        async_add_devices(devices, update_before_add=True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotPhysicalControlLock(MiotSubDevice, LockEntity):
    def __init__(self, parent_device, mapping, params, mitype):
        super().__init__(parent_device, mapping, params, mitype)

    @property
    def is_locked(self):
        return self.extra_state_attributes.get(f"{self._did_prefix}physical_controls_locked") == True

    async def async_lock(self, **kwargs):
        result = await self._parent_device.set_property_new(self._did_prefix + "physical_controls_locked", True)
        if result:
            self._state = STATE_LOCKED
            self._state_attrs[f"{self._did_prefix}physical_controls_locked"] = True
            self._parent_device.schedule_update_ha_state(force_refresh=True)
            self._skip_update = True

    async def async_unlock(self, **kwargs):
        result = await self._parent_device.set_property_new(self._did_prefix + "physical_controls_locked", False)
        if result:
            self._state = STATE_UNLOCKED
            self._state_attrs[f"{self._did_prefix}physical_controls_locked"] = False
            self._parent_device.schedule_update_ha_state(force_refresh=True)
            self._skip_update = True

    @property
    def supported_features(self):
        return 0

    @property
    def state(self):
        return STATE_LOCKED if self.is_locked else STATE_UNLOCKED