"""Platform for light integration."""
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
from homeassistant.components.fan import (
    ATTR_SPEED,
    PLATFORM_SCHEMA,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    SUPPORT_DIRECTION,
    FanEntity)
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
from .switch import BinarySelectorEntity
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

TYPE = 'fan'
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

SCAN_INTERVAL = timedelta(seconds=10)

NEW_FAN = True if StrictVersion(current_version.replace(".dev","a")) >= StrictVersion("2021.2.9") else False
SUPPORT_PRESET_MODE = 8

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
        {'default': MiotFan},
        {'default': MiotSubFan, 'a_l': MiotActionList}
    )

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)

class MiotFan(ToggleableMiotDevice, FanEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._speed = None
        self._mode = None
        self._oscillation = None
        hass.async_add_job(self.create_sub_entities)

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if self._did_prefix + 'oscillate' in self._mapping:
            s |= SUPPORT_OSCILLATE
            if self._did_prefix + 'motor_control' in self._mapping:
                s |= SUPPORT_DIRECTION
        if self._did_prefix + 'speed' in self._mapping:
            s |= (SUPPORT_SET_SPEED if not NEW_FAN else SUPPORT_SET_SPEED)
        if self._did_prefix + 'mode' in self._mapping:
            s |= (SUPPORT_SET_SPEED if not NEW_FAN else SUPPORT_PRESET_MODE)
        return s

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        if NEW_FAN:
            # 这个是假的！！
            return None
        else:
            if 'speed' in self._ctrl_params:
                return list(self._ctrl_params['speed'].keys())
            elif 'mode' in self._ctrl_params:
                return list(self._ctrl_params['mode'].keys())

    @property
    def _speed_list_without_preset_modes(self) -> list:
        if 'stepless_speed' not in self._ctrl_params:
            return list(self._ctrl_params['speed'].keys())
        else:
            return list(range(
                self._ctrl_params['stepless_speed']['value_range'][0],
                self._ctrl_params['stepless_speed']['value_range'][1] + 1,
                self._ctrl_params['stepless_speed']['value_range'][2],
            ))

    @property
    def speed(self):
        """Return the current speed."""
        return (self._speed or self._mode) if not NEW_FAN else self._speed

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset_modes."""
        try:
            return list(self._ctrl_params['mode'].keys())
        except KeyError:
            return []

    @property
    def preset_mode(self):
        """Return the current speed."""
        return self._mode

    # @property
    # def percentage(self):
    #     return None

    @property
    def speed_count(self):
        return len(self._speed_list_without_preset_modes)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillation

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        # result = await self.set_property_new(self._did_prefix + "oscillate",self._ctrl_params['oscillate'][oscillating])
        result = await self.set_property_new(self._did_prefix + "oscillate", oscillating)

        if result:
            self._oscillation = True
            self._skip_update = True

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """旧版HA前端调风速是这个"""
        result = True
        if not self.is_on:
            result &= await self.set_property_new(self._did_prefix + "switch_status", self._ctrl_params['switch_status']['power_on'])

        parameters = []
        if 'from_stepless_speed' in kwargs:
            parameters.append({**{'did': self._did_prefix + "stepless_speed", 'value': speed}, **(self._mapping[self._did_prefix + 'stepless_speed'])})

        elif speed:
            if 'speed' in self._ctrl_params:
                parameters.append({**{'did': self._did_prefix + "speed", 'value': self._ctrl_params['speed'][speed]}, **(self._mapping[self._did_prefix + 'speed'])})
            elif 'mode' in self._ctrl_params:
                parameters.append({**{'did': self._did_prefix + "mode", 'value': self._ctrl_params['mode'][speed]}, **(self._mapping[self._did_prefix + 'mode'])})

        if parameters:
            result &= await self.set_property_new(multiparams = parameters)
        if result:
            self._state = True
            if speed is not None:
                self._speed = speed
            self._skip_update = True

    async def async_set_speed(self, speed: str) -> None:
        """HomeKit调风速是这个，旧版speed形如“Level1”，新版是百分比"""
        if 'stepless_speed' not in self._ctrl_params or not NEW_FAN:
            await self.async_turn_on(speed)
        else:
            await self.async_turn_on(speed, from_stepless_speed = True)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        result = await self.set_property_new(self._did_prefix + "mode", self._ctrl_params['mode'][preset_mode])
        if result:
            self._state = True
            self._mode = preset_mode
            self._skip_update = True

    @property
    def current_direction(self) -> str:
        """Fan direction."""
        return None

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if direction == 'forward':
            d = 'left'
        elif direction == 'reverse':
            d = 'right'
        else:
            d = direction
        if d not in self._ctrl_params['motor_control']:
            raise TypeError(f"Your fan does not support {direction}.")
        await self.set_property_new(self._did_prefix + "motor_control", self._ctrl_params['motor_control'][d])

    # async def async_set_percentage(self, percentage: int) -> None:
    #     """Set the speed percentage of the fan."""
    #     pass

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self._state_attrs.get(self._did_prefix + 'speed')) \
                if 'stepless_speed' not in self._ctrl_params or not NEW_FAN \
                else self._state_attrs.get(self._did_prefix + 'stepless_speed')
        except KeyError:
            self._speed = None
        try:
            self._mode = self.get_key_by_value(self._ctrl_params['mode'],self._state_attrs.get(self._did_prefix + 'mode'))
        except KeyError:
            self._mode = None
        self._oscillation = self._state_attrs.get(self._did_prefix + 'oscillate')

class MiotSubFan(MiotSubToggleableDevice, FanEntity):
    def __init__(self, parent_device, mapping, params, mitype):
        super().__init__(parent_device, mapping, params, mitype)
        self._speed = None
        self._oscillation = None

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if 'oscillate' in self._mapping:
            s |= SUPPORT_OSCILLATE
        if 'speed' in self._mapping:
            s |= (SUPPORT_SET_SPEED if not NEW_FAN else SUPPORT_PRESET_MODE)
        return s

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        if NEW_FAN:
            return None
        else:
            return list(self._ctrl_params['speed'].keys())

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset_modes."""
        return list(self._ctrl_params['speed'].keys())

    @property
    def speed(self):
        """Return the current speed."""
        if not NEW_FAN:
            try:
                self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.extra_state_attributes[self._did_prefix + 'speed'])
            except KeyError:
                self._speed = None
            return self._speed
        else:
            return None

    @property
    def preset_mode(self):
        """Return the current speed."""
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.extra_state_attributes[self._did_prefix + 'speed'])
        except KeyError:
            self._speed = None
        return self._speed

    @property
    def percentage(self):
        return 0

    @property
    def speed_count(self):
        return 1

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self.extra_state_attributes.get(self._did_prefix + 'oscillate')

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        # result = await self.set_property_new(self._did_prefix + "oscillate",self._ctrl_params['oscillate'][oscillating])
        result = await self._parent_device.set_property_new(self._did_prefix + "oscillate", oscillating)

        if result:
            self._oscillation = True
            self._skip_update = True

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        result = await self._parent_device.set_property_new(self._did_prefix + "speed", self._ctrl_params['speed'][preset_mode])
        if result:
            self._state = True
            self._speed = preset_mode
            self._skip_update = True

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        pass


    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        parameters = [{**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]

        if speed:
            parameters.append({**{'did': self._did_prefix + "speed", 'value': self._ctrl_params['speed'][speed]}, **(self._mapping['speed'])})

        result = await self._parent_device.set_property_new(multiparams = parameters)
        if result:
            self._state = True
            self._speed = speed
            self._skip_update = True

class MiotActionList(MiotSubDevice, FanEntity):
    def __init__(self, parent_device, mapping, params, mitype):
        """params is not needed. We keep it here to make the ctor same."""
        super().__init__(parent_device, mapping, {}, mitype)
        self._name_suffix = '动作列表'
        self._action_list = []
        for k, v in mapping.items():
            if 'aiid' in v:
                self._action_list.append(k)
        self._state2 = STATE_ON

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_SET_SPEED if not NEW_FAN else SUPPORT_PRESET_MODE

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._action_list

    @property
    def speed(self):
        """Return the current speed."""
        return None

    @property
    def percentage(self) -> str:
        """Return the current speed."""
        return None

    preset_modes = speed_list
    preset_mode = speed

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self._action_list)

        # @property
        # def _speed_list_without_preset_modes(self) -> list:
        #     return []

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        result = await self._parent_device.call_action_new(*self._mapping[speed].values())
        if result:
            self._state2 = STATE_OFF
            self.schedule_update_ha_state()

    async def async_turn_off(self):
        pass

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.async_turn_on(speed=preset_mode)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        pass

    @property
    def is_on(self):
        return self._state2 == STATE_ON

    @property
    def state(self):
        return self._state2

    @property
    def extra_state_attributes(self):
        return {ATTR_ATTRIBUTION: "在上方列表选择动作。选择后会立即执行。\n操作成功后，开关会短暂回弹。"}

    async def async_update(self):
        await asyncio.sleep(1)
        self._state2 = STATE_ON

class SelectorEntity(MiotSubDevice, FanEntity):
    def __init__(self, parent_device, **kwargs):
        self._parent_device = parent_device
        self._did_prefix = f"{kwargs.get('did_prefix')[:10]}_" if kwargs.get('did_prefix') else ""
        self._field = kwargs.get('field')
        self._value_list = kwargs.get('value_list')
        self._name_suffix = kwargs.get('name') or self._field.replace("_", " ").title()
        self._name = f'{parent_device.name} {self._name_suffix}'
        self._unique_id = f"{parent_device.unique_id}-{kwargs.get('field')}"
        self._entity_id = f"{parent_device._entity_id}-{kwargs.get('field')}"
        self.entity_id = f"{DOMAIN}.{self._entity_id}"
        self._available = True
        self._icon = "mdi:tune"

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_SET_SPEED if not NEW_FAN else SUPPORT_PRESET_MODE

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return list(self._value_list)

    @property
    def speed(self):
        """Return the current speed."""
        return self._parent_device.get_key_by_value(self._value_list, self._parent_device.extra_state_attributes.get(self._did_prefix + self._field))

    @property
    def percentage(self) -> str:
        """Return the current speed."""
        return None

    preset_modes = speed_list
    preset_mode = speed

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self._action_list)

    async def async_turn_on(self, speed = None, **kwargs) -> None:
        result = await self._parent_device.set_property_new(self._did_prefix + self._field, self._value_list[speed])
        if result:
            self._state2 = STATE_OFF
            self.schedule_update_ha_state()

    async def async_turn_off(self):
        pass

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.async_turn_on(speed=preset_mode)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        pass

    @property
    def is_on(self):
        return self._state2 == STATE_ON

    @property
    def state(self):
        return self._state2

    @property
    def extra_state_attributes(self):
        return {ATTR_ATTRIBUTION: f"可在此设置“{self._parent_device.name}”的 {self._field}。开关仅用于反馈操作是否成功，无控制功能。"}

    async def async_update(self):
        await asyncio.sleep(1)
        self._state2 = STATE_ON
