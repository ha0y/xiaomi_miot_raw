"""Platform for light integration."""
import asyncio
import logging
from functools import partial

from collections import OrderedDict
from datetime import timedelta
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
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import GenericMiotDevice, ToggleableMiotDevice, MiotSubToggleableDevice, MiotSubDevice, get_dev_info, dev_info
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
                try:
                    devinfo = await get_dev_info(hass, config.get(CONF_CLOUD)['did'])
                    device_info = dev_info(
                        devinfo['result'][1]['value'],
                        token,
                        devinfo['result'][3]['value'],
                        ""
                    )
                except Exception as ex:
                    _LOGGER.error(f"Failed to get device info for {config.get(CONF_NAME)}")
                    device_info = dev_info(host,token,"","")
        device = MiotFan(miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][host] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    if other_mi_type:

        parent_device = None
        try:
            parent_device = hass.data[DOMAIN]['miot_main_entity'][host]
        except KeyError:
            _LOGGER.warning(f"{host} 的主设备尚未就绪，子设备 {TYPE} 等待主设备加载完毕后才会加载")
            raise PlatformNotReady

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
            s |= SUPPORT_SET_SPEED
        return s

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return list(self._ctrl_params['speed'].keys())

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

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

        # result = await self._try_command(
        #     "Turning the miio device on failed.",
        #     self._device.send,
        #     "set_properties",
        #     parameters,
        # )
        result = await self.set_property_new(multiparams = parameters)
        if result:
            self._state = True
            self._skip_update = True

    async def async_update(self):
        await super().async_update()
        # self._speed = self._ctrl_params['speed'].get(self._state_attrs.get('speed_'))
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
            s |= SUPPORT_SET_SPEED
        return s

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return list(self._ctrl_params['speed'].keys())

    @property
    def speed(self):
        """Return the current speed."""
        try:
            self._speed = self.get_key_by_value(self._ctrl_params['speed'],self.device_state_attributes[self._did_prefix + 'speed'])
        except KeyError:
            self._speed = None
        return self._speed

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

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        parameters = [{**{'did': self._did_prefix + "switch_status", 'value': self._ctrl_params['switch_status']['power_on']},**(self._mapping['switch_status'])}]

        if speed:
            parameters.append({**{'did': self._did_prefix + "speed", 'value': self._ctrl_params['speed'][speed]}, **(self._mapping['speed'])})

        # result = await self._try_command(
        #     "Turning the miio device on failed.",
        #     self._device.send,
        #     "set_properties",
        #     parameters,
        # )
        result = await self._parent_device.set_property_new(multiparams = parameters)
        if result:
            self._state = True
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
        return SUPPORT_SET_SPEED

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._action_list

    @property
    def speed(self):
        """Return the current speed."""
        return None

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        result = await self._parent_device.call_action_new(*self._mapping[speed].values())
        if result:
            self._state2 = STATE_OFF
            self.schedule_update_ha_state()

    async def async_turn_off(self):
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