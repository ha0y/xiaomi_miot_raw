"""Platform for camera integration."""
import asyncio
import logging
from functools import partial

from datetime import timedelta
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.camera import (
    SUPPORT_ON_OFF, SUPPORT_STREAM,
    PLATFORM_SCHEMA,
    Camera
)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice
import miio
import copy

from .basic_dev_class import (
    GenericMiotDevice,
    ToggleableMiotDevice,
    MiotSubDevice,
    MiotSubToggleableDevice,
    MiotIRDevice,
)
from . import async_generic_setup_platform
from .deps.const import (
    DOMAIN,
    ATTR_SYSSTATUS,
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

TYPE = 'camera'

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
    await async_generic_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info,
        TYPE,
        {'default': MiotCamera}
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)


class MiotCamera(ToggleableMiotDevice, Camera):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._is_on = False

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF

    @property
    def is_recording(self) -> bool:
        return False

    @property
    def is_streaming(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self) -> None:
        """Turn on."""
        prm = self._ctrl_params['switch_status']['power_on']
        d: miio.chuangmi_camera.ChuangmiCamera = self._device
        d.send("set_" + ATTR_SYSSTATUS, ['normal'])
        result = await self.set_property_new(self._did_prefix + "switch_status", prm)
        if result:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off."""
        prm = self._ctrl_params['switch_status']['power_on']
        d: miio.chuangmi_camera.ChuangmiCamera = self._device
        d.send("set_" + ATTR_SYSSTATUS, ['sleep'])
        result = await self.set_property_new(self._did_prefix + "switch_status", prm)
        if result:
            self._state = True
            self.async_write_ha_state()
