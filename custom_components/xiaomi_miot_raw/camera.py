"""Platform for camera integration."""
import asyncio
import logging
from functools import partial
import collections

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


class MiotCamera(GenericMiotDevice, Camera):
    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str | None:
        pass

    def camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        pass

    def turn_off(self) -> None:
        pass

    def turn_on(self) -> None:
        pass

    def enable_motion_detection(self) -> None:
        pass

    def disable_motion_detection(self) -> None:
        pass

    def __init__(self, device, config, device_info, hass, main_mi_type):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        Camera.__init__(self)
        self._state = False

    @property
    def should_poll(self):
        return True

    def update(self):
        return True

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF

    @property
    def is_recording(self) -> bool:
        return self._state

    @property
    def is_streaming(self) -> bool:
        return self._state

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_turn_on(self) -> None:
        self._state = True
        # await self.async_do_turn_on(True)

    async def async_turn_off(self) -> None:
        self._state = False
        # await self.async_do_turn_on(False)

    async def async_do_turn_on(self, new_status) -> None:
        d: miio.chuangmi_camera.ChuangmiCamera = self._device
        if new_status:
            cmd = "normal"
        else:
            cmd = "sleep"
        result = d.send("set_" + ATTR_SYSSTATUS, [cmd])
        if result != ['ok']:
            _LOGGER.warning("result for send {}, {}".format(cmd, result))
            return

        self._state = new_status
        self.async_write_ha_state()
