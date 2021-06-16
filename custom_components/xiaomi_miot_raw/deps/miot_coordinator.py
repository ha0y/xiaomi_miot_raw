import asyncio
import json
import logging
from datetime import timedelta, datetime
from functools import partial
from dataclasses import dataclass

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant.const import *
from homeassistant.core import callback
from homeassistant.components import persistent_notification
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client, discovery
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import color
from miio.exceptions import DeviceException
from .miio_new import MiotDevice
import copy
import math
from collections import OrderedDict

from .const import (
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
    SUPPORTED_DOMAINS,
)

from .xiaomi_cloud_new import *
from .xiaomi_cloud_new import MiCloud
from asyncio.exceptions import CancelledError

_LOGGER = logging.getLogger(__name__)

class MiotCloudCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device.
       One for each account."""

    def __init__(self, hass, cloud: MiCloud):
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{cloud.auth['user_id']}",
            update_interval=timedelta(seconds=6),
        )
        self._cloud_instance = cloud
        self._error_count = 0
        self._fixed_list = []
        self._waiting_list = [] # 请求的params
        self._results = {}

    def add_fixed_by_mapping(self, cloudconfig, mapping):
        did = cloudconfig.get("did")
        for value in mapping.values():
            if 'aiid' not in value:
                self._fixed_list.append({**{'did':did},**value})


    async def _async_update_data(self):
        """ 覆盖定期执行的方法 """
        # _LOGGER.info(f"{self._name} is updating from cloud.")
        data1 = {}
        data1['datasource'] = 1
        data1['params'] = self._fixed_list + self._waiting_list
        data2 = json.dumps(data1,separators=(',', ':'))

        a = await self._cloud_instance.get_props(data2)

        # dict1 = {}
        # statedict = {}
        if a:
            # self._available = True
            result = a['result']
            results = {}
            for item in result:
                if item['did'] not in results:
                    results[item['did']] = [item]
                else:
                    results[item['did']].append(item)
            self._waiting_list = []
            return results

class MiotEventCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, cloud: MiCloud, cloud_config, item):
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{cloud.auth['user_id']}-event-{item[0]}",
            update_interval=timedelta(seconds=6),
        )
        self._cloud_instance = cloud
        self._cloud = cloud_config
        # self._mapping = mapping
        self._item = item
        self._error_count = 0
        self._results = {}

    async def _async_update_data(self):
        result = await self._cloud_instance.get_user_device_data(
            self._cloud.get("did"),
            self._item[1]['key'],
            self._item[1]['type'],
            self._cloud.get("server_location"),
        )
        if result is None:
            return None
        if result['code'] != 0:
            _LOGGER.error(result)
            return result
        else:
            result2 = [(datetime.fromtimestamp(item['time']).isoformat(sep=' '), item['value']) for item in result['result']]
        # self._results[k] = result2
            return result2