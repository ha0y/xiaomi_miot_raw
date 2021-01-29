import asyncio
import json
import logging
from functools import partial

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
)

DOMAIN = 'xiaomi_miot_raw'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT switch"
DATA_KEY = "switch." + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UPDATE_INSTANT, default=True): cv.boolean,
        vol.Optional(CONF_CLOUD): vol.All(),
        
        vol.Required(CONF_MAPPING):vol.All(),
        vol.Required(CONF_CONTROL_PARAMS):vol.All(),
        vol.Optional('cloud_write'):vol.All(),

    }
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
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

class MiotSwitch(ToggleableMiotDevice, SwitchEntity):
    pass
