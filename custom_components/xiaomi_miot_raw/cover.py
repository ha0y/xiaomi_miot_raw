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
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

import copy
from . import GenericMiotDevice, dev_info
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
        device = MiotCover(miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    else:
        _LOGGER.error(f"cover只能作为主设备！请检查{config.get(CONF_NAME)}配置")

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    # config[CONF_MAPPING] = config[CONF_MAPPING][TYPE]
    # config[CONF_CONTROL_PARAMS] = config[CONF_CONTROL_PARAMS][TYPE]
    await async_setup_platform(hass, config, async_add_entities)

class MiotCover(GenericMiotDevice, CoverEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._current_position = None
        self._target_position = None
        self._action = None
        # self._hass = hass
        # self._cloud = config.get(CONF_CLOUD)
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
        return self._current_position or 50

    @property
    def is_closed(self):
        """Return if the cover is closed, same as position 0."""
        # try:
        return self._current_position == 0
        # except (ValueError, TypeError):
            # return None
    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        try:
            return self._action == self._ctrl_params['motor_status']['close']
        except KeyError:
            return None

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        try:
            return self._action == self._ctrl_params['motor_status']['open']
        except KeyError:
            return None

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        result = await self.set_property_new(self._did_prefix + "motor_control",self._ctrl_params['motor_control']['open'])
        if result:
            # self._skip_update = True
            try:
                self._action = self._ctrl_params['motor_status']['open']
            except KeyError as ex:
                _LOGGER.error(ex)
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

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        self._current_position = self._state_attrs.get(self._did_prefix + 'current_position')
        if self.is_closing or self.is_opening:
            self.async_update = self._throttle1
        else:
            self.async_update = self._throttle10
        self._action = self._state_attrs.get(self._did_prefix + 'motor_status')

    async def _async_update(self):
        if self._update_instant is False or self._skip_update:
            self._skip_update = False
            return
        await super().async_update()
