import asyncio
import json
import logging
from functools import partial

import json
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import ToggleableMiotDevice
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
)
import copy

TYPE = 'switch'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)

    _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])

    try:
        miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        device = MiotSwitch(miio_device, config, device_info, hass)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DOMAIN]['entities'][device.unique_id] = device
    async_add_entities([device], update_before_add=True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    config[CONF_MAPPING] = config[CONF_MAPPING][TYPE]
    config[CONF_CONTROL_PARAMS] = config[CONF_CONTROL_PARAMS][TYPE]
    await async_setup_platform(hass, config, async_add_entities)

class MiotSwitch(ToggleableMiotDevice, SwitchEntity):
    def __init__(self, device, config, device_info, hass):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass)
