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
from homeassistant.components import climate
from homeassistant.components.climate import (ClimateEntity, PLATFORM_SCHEMA)
from homeassistant.components.climate.const import *
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

import copy
from . import GenericMiotDevice, ToggleableMiotDevice, dev_info
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

TYPE = 'climate'
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)


HVAC_MAPPING = {
    HVAC_MODE_OFF:  ['Off', 'Idle', 'None'],
    HVAC_MODE_AUTO: ['Auto', 'Auto-tempature'],
    HVAC_MODE_COOL: ['Cool'],
    HVAC_MODE_HEAT: ['Heat'],
    HVAC_MODE_DRY:  ['Dry'],
    HVAC_MODE_FAN_ONLY: ['Fan', 'Fan-tempature'],
    HVAC_MODE_HEAT_COOL:['HeatCool'],
}

SWING_MAPPING = [
    "Off",
    "Vertical",
    "Horizontal",
    "Both"
]

SCAN_INTERVAL = timedelta(seconds=10)
# pylint: disable=unused-argument
@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)

    mappingnew = {}

    main_mi_type = None
    this_mi_type = []

    for t in MAP[TYPE]:
        if mapping.get(t):
            this_mi_type.append(t)
        if 'main' in (params.get(t) or ""):
            main_mi_type = t

    if main_mi_type or type(params) == OrderedDict:
        for k,v in mapping.items():
            for kk,vv in v.items():
                mappingnew[f"{k[:10]}_{kk}"] = vv

        _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])
        if type(params) == OrderedDict:
            miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        else:
            miio_device = MiotDevice(ip=host, token=token, mapping=mappingnew)
        try:
            if host == DUMMY_IP and token == DUMMY_TOKEN:
                raise DeviceException
            device_info = miio_device.info()
            model = device_info.model
            _LOGGER.info(
                "%s %s %s detected",
                model,
                device_info.firmware_version,
                device_info.hardware_version,
            )

        except DeviceException as de:
            if not config.get(CONF_CLOUD):
                _LOGGER.warn(de)
                raise PlatformNotReady
            else:
                if not (di := config.get('cloud_device_info')):
                    _LOGGER.error(f"未能获取到设备信息，请删除 {config.get(CONF_NAME)} 重新配置。")
                    raise PlatformNotReady
                else:
                    device_info = dev_info(
                        di['model'],
                        di['mac'],
                        di['fw_version'],
                        ""
                    )
        device = MiotClimate(miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][host] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    else:
        _LOGGER.error(f"climate只能作为主设备！请检查{config.get(CONF_NAME)}配置")

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

async def async_unload_entry(hass, config_entry, async_add_entities):
    return True

class MiotClimate(ToggleableMiotDevice, ClimateEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._speed = None
        self._target_temperature = None
        self._target_humidity = None
        self._unit_of_measurement = TEMP_CELSIUS
        self._preset = None
        self._preset_modes = None
        self._current_temperature = None
        self._current_humidity = None
        self._current_fan_mode = None
        self._hvac_action = None
        self._hvac_mode = None
        self._aux = None
        self._current_swing_mode = None
        self._fan_modes = []
        self._hvac_modes = None
        self._swing_modes = []
        if self._did_prefix + 'vertical_swing' in self._mapping and \
            self._did_prefix + 'horizontal_swing' in self._mapping:
                self._swing_modes = ["Off", "Vertical", "Horizontal", "Both"]
        elif self._did_prefix + 'vertical_swing' in self._mapping and \
            not self._did_prefix + 'horizontal_swing' in self._mapping:
                self._swing_modes = ["Off", "Vertical"]
        elif not self._did_prefix + 'vertical_swing' in self._mapping and \
            self._did_prefix + 'horizontal_swing' in self._mapping:
                self._swing_modes = ["Off", "Horizontal"]

        try:
            self._target_temperature_step = self._ctrl_params['target_temperature']['value_range'][2]
        except:
            self._target_temperature_step = 1

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if self._did_prefix + 'target_temperature' in self._mapping:
            s |= SUPPORT_TARGET_TEMPERATURE
        if self._did_prefix + 'speed' in self._mapping:
            s |= SUPPORT_FAN_MODE
        if self._did_prefix + 'preset' in self._mapping:
            s |= SUPPORT_PRESET_MODE
        if self._did_prefix + 'target_humidity' in self._mapping:
            s |= SUPPORT_TARGET_HUMIDITY
        if self._swing_modes:
            s |= SUPPORT_SWING_MODE
        # if 'aux_heat' in self._mapping:
        #     s |= SUPPORT_AUX_HEAT
        # if 'temprature_range' in self._mapping:
        #     s |= SUPPORT_TARGET_TEMPERATURE_RANGE

        # s = SUPPORT_TARGET_TEMPERATURE|SUPPORT_FAN_MODE|SUPPORT_PRESET_MODE|SUPPORT_SWING_MODE
        return s

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the temperature we try to reach."""
        return self._target_temperature_step

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._ctrl_params['target_temperature']['value_range'][1]

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._ctrl_params['target_temperature']['value_range'][0]

    @property
    def min_temp(self):
        """Return the lowbound target temperature we try to reach."""
        return self._ctrl_params['target_temperature']['value_range'][0]

    @property
    def max_temp(self):
        """Return the lowbound target temperature we try to reach."""
        return self._ctrl_params['target_temperature']['value_range'][1]

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_action

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        return self._hvac_mode

    @property
    def state(self):
        if not self.is_on:
            return STATE_OFF
        else:
            return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        try:
            return [next(a[0] for a in HVAC_MAPPING.items() if b in a[1]) for b in self._ctrl_params['mode']] + [HVAC_MODE_OFF]
        except:
            _LOGGER.error(f"Modes {self._ctrl_params['mode']} contains unsupported ones. Please report this message to the developer.")

    @property
    def preset_mode(self):
        """Return preset mode."""
        return self._preset

    @property
    def preset_modes(self):
        """Return preset modes."""
        # return self._preset_modes
        return ["home", "eco"]

    @property
    def is_aux_heat(self):
        """Return true if aux heat is on."""
        return self._aux

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return list(self._ctrl_params['speed'].keys())

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return self._swing_modes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            result = await self.set_property_new(self._did_prefix + "target_temperature", kwargs.get(ATTR_TEMPERATURE))
            if result:
                self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
                self.async_write_ha_state()

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        self._target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        swm = SWING_MAPPING.index(swing_mode)
        parameters = []
        if 'Vertical' in self._swing_modes:
            parameters.append({
                **{'did': self._did_prefix + "vertical_swing", 'value': bool(swm & 1)},
                **(self._mapping[self._did_prefix + 'vertical_swing'])
            })
        if 'Horizontal' in self._swing_modes:
            parameters.append({
                **{'did': self._did_prefix + "horizontal_swing", 'value': bool(swm >> 1)},
                **(self._mapping[self._did_prefix + 'horizontal_swing'])
            })
        result = await self.set_property_new(multiparams = parameters)
        if result:
            self._current_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        result = await self.set_property_new(self._did_prefix + "speed", self._ctrl_params['speed'][fan_mode])

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            result = await self.async_turn_off()
        else:
            parameters = []
            if not self.is_on:
                parameters.append({
                    **{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},
                    **(self._mapping[self._did_prefix + 'switch_status'])
                })

            modevalue = None
            for item in HVAC_MAPPING[hvac_mode]:
                if item in self._ctrl_params['mode']:
                    modevalue = self._ctrl_params['mode'].get(item)
                    break
            if not modevalue:
                _LOGGER.error(f"Failed to set {self._name} to mode {hvac_mode} because cannot find it in params.")
                return False

            parameters.append({
                **{'did': self._did_prefix + "mode", 'value': modevalue},
                **(self._mapping[self._did_prefix + 'mode'])
            })
            result = await self.set_property_new(multiparams = parameters)
            if result:
                self._hvac_mode = hvac_mode
                self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Update preset_mode on."""
        self._preset = preset_mode
        self.async_write_ha_state()

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._aux = True
        self.async_write_ha_state()

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._aux = False
        self.async_write_ha_state()

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        try:
            self._target_temperature = self._state_attrs.get(self._did_prefix + 'target_temperature')
        except:
            pass
        try:
            self._current_temperature = self._state_attrs.get('environmen_temperature')
            if not self._current_temperature:
                if src := self._ctrl_params.get('current_temp_source'):
                    try:
                        state = self.hass.states.get(src)
                        self._current_temperature = float(state.state)
                    except Exception as ex:
                        _LOGGER.error(f"{self._name} 's temperature source ({src}) is invalid! Expect a number, got {state.state if state else None}. {ex}")
                        self._current_temperature = -1
                else:
                    self._current_temperature = self._target_temperature
        except Exception as ex:
            _LOGGER.error(ex)
        try:
            self._current_fan_mode = self.get_key_by_value(self._ctrl_params['speed'], self._state_attrs.get(self._did_prefix + 'speed'))
        except:
            pass
        try:
            hvac_mode2 = self.get_key_by_value(self._ctrl_params['mode'], self._state_attrs.get(self._did_prefix + 'mode'))
            for k,v in HVAC_MAPPING.items():
                if hvac_mode2 in v:
                    self._hvac_mode = k
        except:
            pass
        if self._swing_modes:
            ver = self._state_attrs.get(self._did_prefix + 'vertical_swing') or 0
            hor = self._state_attrs.get(self._did_prefix + 'horizontal_swing') or 0
            self._current_swing_mode = SWING_MAPPING[hor << 1 | ver]
