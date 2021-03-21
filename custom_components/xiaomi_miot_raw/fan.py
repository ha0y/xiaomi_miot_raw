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
    FanEntity)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice

from . import GenericMiotDevice, ToggleableMiotDevice, MiotSubToggleableDevice, MiotSubDevice, dev_info
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
    """Set up the fan from config."""

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
        if main_mi_type == 'washer':
            device = MiotWasher(miio_device, config, device_info, hass, main_mi_type)
        else:
            device = MiotFan(miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    if other_mi_type:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(f'{host}-{config.get(CONF_NAME)}'):
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
            if item == 'a_l':
                devices.append(MiotActionList(parent_device, mapping.get(item), item))
            else:
                devices.append(MiotSubFan(parent_device, mapping.get(item), params.get(item), item))
        async_add_devices(devices, update_before_add=True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    # config[CONF_MAPPING] = config[CONF_MAPPING][TYPE]
    # config[CONF_CONTROL_PARAMS] = config[CONF_CONTROL_PARAMS][TYPE]
    await async_setup_platform(hass, config, async_add_entities)

class MiotFan(ToggleableMiotDevice, FanEntity):
    """ TODO stepless speed """

    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._speed = None
        self._oscillation = None

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if self._did_prefix + 'oscillate' in self._mapping:
            s |= SUPPORT_OSCILLATE
        if self._did_prefix + 'speed' in self._mapping:
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
    def speed(self):
        """Return the current speed."""
        return self._speed if not NEW_FAN else None

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset_modes."""
        return list(self._ctrl_params['speed'].keys())

    @property
    def preset_mode(self):
        """Return the current speed."""
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.device_state_attributes[self._did_prefix + 'speed'])
        except KeyError:
            self._speed = None
        return self._speed

    @property
    def percentage(self):
        return None

    @property
    def speed_count(self):
        return len(self.preset_modes)

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
        """Turn on the entity."""
        parameters = [{**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping[self._did_prefix + 'switch_status'])}]

        if speed:
            parameters.append({**{'did': self._did_prefix + "speed", 'value': self._ctrl_params['speed'][speed]}, **(self._mapping[self._did_prefix + 'speed'])})

        result = await self.set_property_new(multiparams = parameters)
        if result:
            self._state = True
            self._speed = speed
            self._skip_update = True

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        result = await self.set_property_new(self._did_prefix + "speed", self._ctrl_params['speed'][preset_mode])
        if result:
            self._state = True
            self._speed = preset_mode
            self._skip_update = True

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        pass

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self._state_attrs.get(self._did_prefix + 'speed'))
        except KeyError:
            pass
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
                self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.device_state_attributes[self._did_prefix + 'speed'])
            except KeyError:
                self._speed = None
            return self._speed
        else:
            return None

    @property
    def preset_mode(self):
        """Return the current speed."""
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.device_state_attributes[self._did_prefix + 'speed'])
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
        return self.device_state_attributes.get(self._did_prefix + 'oscillate')

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        # result = await self.set_property_new(self._did_prefix + "oscillate",self._ctrl_params['oscillate'][oscillating])
        result = await self.set_property_new(self._did_prefix + "oscillate", oscillating)

        if result:
            self._oscillation = True
            self._skip_update = True

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        result = await self.set_property_new(self._did_prefix + "speed", self._ctrl_params['speed'][preset_mode])
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
    def __init__(self, parent_device, mapping, mitype):
        super().__init__(parent_device, mapping, {}, mitype)
        self._name = f'{parent_device.name} 动作列表'
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
    def device_state_attributes(self):
        return {ATTR_ATTRIBUTION: "在上方列表选择动作。选择后会立即执行。\n操作成功后，开关会短暂回弹。"}

    async def async_update(self):
        await asyncio.sleep(1)
        self._state2 = STATE_ON

class MiotWasher(ToggleableMiotDevice, FanEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._speed = None
        self._oscillation = None
        if 'switch_status' in self._ctrl_params:
            self._assumed_state = False
        else:
            self._assumed_state = True

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_SET_SPEED if not NEW_FAN else SUPPORT_PRESET_MODE

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        if NEW_FAN:
            return None
        else:
            return list(self._ctrl_params['speed'].keys())

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed if not NEW_FAN else None

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset_modes."""
        return list(self._ctrl_params['speed'].keys())

    @property
    def preset_mode(self):
        """Return the current speed."""
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.device_state_attributes[self._did_prefix + 'speed'])
        except KeyError:
            self._speed = None
        return self._speed

    @property
    def percentage(self):
        return None

    @property
    def speed_count(self):
        return len(self.preset_modes)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillation

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return self._assumed_state

    async def async_turn_on(self, speed: str = None, **kwargs):
        """Turn on."""
        if 'switch_status' in self._ctrl_params:
            await super().async_turn_on()
        else:
            try:
                result = await self.call_action_new(*(self._mapping['a_l_' + self._did_prefix + 'start_wash'].values()))
            except Exception as ex:
                _LOGGER.error(ex)
        if speed:
            await self.async_set_preset_mode(speed)

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        if 'switch_status' in self._ctrl_params:
            await super().async_turn_off()
        else:
            try:
                result = await self.call_action_new(*(self._mapping['a_l_' + self._did_prefix + 'pause'].values()))
            except Exception as ex:
                raise NotImplementedError(ex)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        result = await self.set_property_new(self._did_prefix + "speed", self._ctrl_params['speed'][preset_mode])
        if result:
            self._speed = preset_mode
            self._skip_update = True