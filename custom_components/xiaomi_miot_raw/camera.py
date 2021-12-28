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
    def enable_motion_detection(self) -> None:
        pass

    def disable_motion_detection(self) -> None:
        pass

    def __init__(self, device, config, device_info, hass, main_mi_type):
        self._device: miio.chuangmi_camera.ChuangmiCamera = None  # Just for type hint
        GenericMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        Camera.__init__(self)
        self._state: bool = True

    @property
    def should_poll(self):
        return True

    async def async_update(self):
        _LOGGER.debug("Start camera.async_update")
        device_status = self.get_devicestatus()
        # sleep will return [{'sysstatus': 'sleep'}]
        # otherwise will return all other status
        self._state = (len(device_status) > 1)
        _LOGGER.debug(f"camera.async_update result: {self._state}")

    def get_devicestatus(self):
        return self._device.send('get_devicestatus', {
            'alarmsensitivity': "",
            'cameraprompt': "",
            'flip': "",
            'infraredlight': "",
            'ledstatus': "",
            'recordtype': "",
            'wakeuplevel': "",
        })

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF

    @property
    def is_recording(self) -> bool:
        return self._state

    @property
    def is_streaming(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        return True

    async def async_turn_on(self) -> None:
        await self.async_do_turn_on(True)

    async def async_turn_off(self) -> None:
        await self.async_do_turn_on(False)

    async def async_do_turn_on(self, new_status) -> None:
        _LOGGER.debug(f"Start camera.async_do_turn_on( {new_status} )")

        if new_status:
            cmd = "normal"
        else:
            cmd = "sleep"
        result = self._device.send("set_" + ATTR_SYSSTATUS, [cmd])
        if result != ['ok']:
            _LOGGER.warning("result for send {}, {}".format(cmd, result))
            return

        self._state = new_status
        self.schedule_update_ha_state()
