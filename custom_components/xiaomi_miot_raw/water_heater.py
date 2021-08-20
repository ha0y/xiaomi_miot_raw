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
from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
    PLATFORM_SCHEMA,
)
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
from .climate import MiotClimate
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

TYPE = 'water_heater'
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
    await async_generic_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info,
        TYPE,
        {'default': MiotWaterHeater},
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

async def async_unload_entry(hass, config_entry, async_add_entities):
    return True

class MiotWaterHeater(ToggleableMiotDevice, WaterHeaterEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._target_temperature = None
        self._unit_of_measurement = TEMP_CELSIUS
        self._away = None
        self._current_operation = None
        self._current_temperature = None
        hass.async_add_job(self.create_sub_entities)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        s = SUPPORT_OPERATION_MODE
        if self._did_prefix + 'target_temperature' in self._mapping:
            s |= SUPPORT_TARGET_TEMPERATURE
        return s

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def min_temp(self):
        """Return the lowbound target temperature we try to reach."""
        return self._ctrl_params['target_temperature']['value_range'][0]

    @property
    def max_temp(self):
        """Return the lowbound target temperature we try to reach."""
        return self._ctrl_params['target_temperature']['value_range'][1]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return (["on","off"] if self._did_prefix + 'switch_status' in self._mapping else []) + (list(self._ctrl_params['mode'].keys()) if 'mode' in self._ctrl_params else [])

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            result = await self.set_property_new(self._did_prefix + "target_temperature", kwargs.get(ATTR_TEMPERATURE))
            if result:
                self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
                self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        if operation_mode == 'on':
            await self.async_turn_on()
            if self._state == True:
                self._current_operation = 'on'
        elif operation_mode == 'off':
            await self.async_turn_off()
            if self._state == False:
                self._current_operation = 'off'
        else:
            result = await self.set_property_new(self._did_prefix + "mode", self._ctrl_params['mode'][operation_mode])
            if result:
                self._current_operation = operation_mode
                self.async_write_ha_state()

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        try:
            self._target_temperature = self._state_attrs.get(self._did_prefix + 'target_temperature')
        except:
            pass
        try:
            self._current_temperature = self._state_attrs.get(self._did_prefix + 'temperature')
        except:
            pass
        try:
            o = self._state_attrs.get(self._did_prefix + 'mode')
            if o in ('on','off'):
                self._current_operation = o
            elif o is not None:
                self.get_key_by_value(self._ctrl_params['mode'], o)
        except:
            pass
