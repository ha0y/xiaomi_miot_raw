import asyncio
import json
import logging
from collections import OrderedDict
from datetime import timedelta
from functools import partial
from typing import Optional

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant.components import vacuum
from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    StateVacuumEntity,
    VacuumEntity,
    PLATFORM_SCHEMA
)
from homeassistant.components.climate.const import *
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client
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

TYPE = 'vacuum'
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

STATE_MAPPING = {
    STATE_CLEANING:  ['Sweeping'],
    STATE_DOCKED:    ['Charging'],
    STATE_IDLE:      ['Idle'],
    STATE_PAUSED:    ['Paused'],
    STATE_RETURNING: ['Go Charging'],
}

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
        {'default': MiotVacuum},
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

async def async_unload_entry(hass, config_entry, async_add_entities):
    return True

class MiotVacuum(GenericMiotDevice, StateVacuumEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._state = None
        self._battery_level = None
        self._status = ""
        self._fan_speed = None
        hass.async_add_job(self.create_sub_entities)

    @property
    def supported_features(self):
        """Flag supported features."""
        s = 0
        if 'a_l_vacuum_start_sweep' in self._mapping:
            s |= SUPPORT_START
        if 'a_l_vacuum_pause_sweeping' in self._mapping:
            s |= SUPPORT_PAUSE
        if 'a_l_vacuum_stop_sweeping' in self._mapping:
            s |= SUPPORT_STOP
        if self._did_prefix + 'mode' in self._mapping:
            s |= SUPPORT_FAN_SPEED
        if self._did_prefix + 'battery_level' in self._mapping or \
            'battery_battery_level' in self._mapping:
            s |= SUPPORT_BATTERY
        if 'a_l_battery_start_charge' in self._mapping:
            s |= SUPPORT_RETURN_HOME
        if 'a_l_voice_find_device' in self._mapping or \
            'a_l_identify_identify' in self._mapping:
            s |= SUPPORT_LOCATE
        return s

    @property
    def state(self):
        """Return the current state of the vacuum."""
        return self._state

    @property
    def battery_level(self):
        """Return the current battery level of the vacuum."""
        return self._battery_level

    @property
    def fan_speed(self):
        """Return the current fan speed of the vacuum."""
        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Return the list of supported fan speeds."""
        return list(self._ctrl_params['mode'].keys())

    async def async_start(self):
        """Start or resume the cleaning task."""
        if self.supported_features & SUPPORT_START == 0:
            return

        result = await self.call_action_new(*(self._mapping['a_l_vacuum_start_sweep'].values()))
        if result:
            self._state = STATE_CLEANING
            self.schedule_update_ha_state()


    async def async_pause(self):
        """Pause the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return

        result = await self.call_action_new(*(self._mapping['a_l_vacuum_pause_sweeping'].values()))
        if result:
            self._state = STATE_PAUSED
            self.schedule_update_ha_state()

    async def async_stop(self, **kwargs):
        """Stop the cleaning task, do not return to dock."""
        if self.supported_features & SUPPORT_STOP == 0:
            return

        result = await self.call_action_new(*(self._mapping['a_l_vacuum_stop_sweeping'].values()))
        if result:
            self._state = STATE_IDLE
            self.schedule_update_ha_state()

    async def async_return_to_base(self, **kwargs):
        """Return dock to charging base."""
        if self.supported_features & SUPPORT_RETURN_HOME == 0:
            return

        result = await self.call_action_new(*(self._mapping['a_l_battery_start_charge'].values()))
        if result:
            self._state = STATE_RETURNING
            self.schedule_update_ha_state()

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        raise NotImplementedError()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set the vacuum's fan speed."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return

        result = await self.set_property_new(self._did_prefix + "mode", self._ctrl_params['mode'][fan_speed])
        if result:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    async def async_locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if 'a_l_voice_find_device' in self._mapping:
            result = await self.call_action_new(*(self._mapping['a_l_voice_find_device'].values()))
        elif 'a_l_identify_identify' in self._mapping:
            result = await self.call_action_new(*(self._mapping['a_l_identify_identify'].values()))
        else:
            return

        if result:
            self.schedule_update_ha_state()

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        try:
            for k,v in STATE_MAPPING.items():
                if self._state_attrs.get(self._did_prefix + 'status') in v:
                    self._state = k
        except:
            pass
        try:
            self._battery_level = self._state_attrs.get(self._did_prefix + 'battery_level') or \
                self._state_attrs.get('battery_battery_level')
        except:
            pass
        try:
            self._fan_speed = self.get_key_by_value(self._ctrl_params['mode'],self._state_attrs.get(self._did_prefix + 'mode'))
        except KeyError:
            self._fan_speed = None
