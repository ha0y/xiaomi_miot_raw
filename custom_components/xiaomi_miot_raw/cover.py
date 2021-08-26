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
from homeassistant.components.cover import (
    DEVICE_CLASS_CURTAIN, DOMAIN,
    ENTITY_ID_FORMAT, PLATFORM_SCHEMA,
    SUPPORT_CLOSE, SUPPORT_OPEN,
    SUPPORT_SET_POSITION, SUPPORT_STOP,
    CoverDevice, CoverEntity)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.util import Throttle
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice

import copy
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
TYPE = 'cover'
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

SCAN_INTERVAL = timedelta(seconds=2)
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
        {'default': MiotCover},
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotCover(GenericMiotDevice, CoverEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._current_position = None
        self._target_position = None
        self._action = None
        self._throttle1 = Throttle(timedelta(seconds=1))(self._async_update)
        self._throttle10 = Throttle(timedelta(seconds=10))(self._async_update)
        self.async_update = self._throttle10

    @property
    def should_poll(self):
        """The cover should always be pulled."""
        return True

    @property
    def available(self):
        """Return true when state is known."""
        return True

    @property
    def supported_features(self):
        if self._did_prefix + 'target_position' in self._mapping:
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        else:
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        if self._current_position is None:
            return 50
        return self._current_position

    @property
    def is_closed(self):
        """Return if the cover is closed, same as position 0."""
        return self._current_position == 0

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        if type(self._action) == str:
            return 'down' in self._action.lower() \
                or 'dowm' in self._action.lower() \
                or 'clos' in self._action.lower()
        elif type(self._action) == int:
            try:
                return self._action == self._ctrl_params['motor_status']['close']
            except KeyError:
                return False
        return False

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        if type(self._action) == str:
            return 'up' in self._action.lower() \
                or 'open' in self._action.lower()
        elif type(self._action) == int:
            try:
                return self._action == self._ctrl_params['motor_status']['open']
            except KeyError:
                return False
        return False

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        result = await self.set_property_new(self._did_prefix + "motor_control",self._ctrl_params['motor_control']['open'])
        if result:
            # self._skip_update = True
            try:
                self._action = self._ctrl_params['motor_status']['open']
            except KeyError as ex:
                pass
            self.async_write_ha_state()
            self.async_update = self._throttle1
            self.schedule_update_ha_state(force_refresh=True)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        result = await self.set_property_new(self._did_prefix + "motor_control",self._ctrl_params['motor_control']['close'])
        if result:
            try:
                self._action = self._ctrl_params['motor_status']['close']
            except KeyError:
                pass
            self.async_write_ha_state()
            self.async_update = self._throttle1
            self.schedule_update_ha_state(force_refresh=True)

    async def async_stop_cover(self, **kwargs):
        """Close the cover."""
        result = await self.set_property_new(self._did_prefix + "motor_control",self._ctrl_params['motor_control']['stop'])
        if result:
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Set the cover."""
        result = await self.set_property_new(self._did_prefix + "target_position",kwargs['position'])

        if result:
            self._skip_update = True
            
    def _update_current_position(self):
        p = self._state_attrs.get(self._did_prefix + 'current_position')
        if p is None:
            self._current_position = None
            return
        range_min = 0
        range_max = 100
        try:
            range_min = self._ctrl_params['current_position']['value_range'][0]
            range_max = self._ctrl_params['current_position']['value_range'][1]
        except KeyError:
            pass
        if p < range_min or range_max < p:
            self._current_position = None
            return
        if 0 != range_min and range_max != 100:
            p = (p - range_min) / (range_max - range_min) * 100
        if self._ctrl_params.get('reverse_position_percentage', False):
            p = 100 - p
        self._current_position = p;

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        self._update_current_position()
        
        if self.is_closing or self.is_opening:
            self.async_update = self._throttle1
        else:
            self.async_update = self._throttle10
        self._action = self._state_attrs.get(self._did_prefix + 'motor_status') or \
            self._state_attrs.get(self._did_prefix + 'status')

    async def _async_update(self):
        if self._update_instant is False or self._skip_update:
            self._skip_update = False
            return
        await super().async_update()
