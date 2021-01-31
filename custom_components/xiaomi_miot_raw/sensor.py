import asyncio
import logging
from collections import defaultdict
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ENTITY_ID, CONF_HOST, CONF_NAME,
                                 CONF_TOKEN)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import GenericMiotDevice
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

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT sensor"
DATA_KEY = "sensor." + DOMAIN

CONF_SENSOR_PROPERTY = "sensor_property"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_DEFAULT_PROPERTIES = "default_properties"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

ATTR_PROPERTIES = "properties"
ATTR_SENSOR_PROPERTY = "sensor_property"

# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
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

        device = MiotSensor(miio_device, config, device_info)
        devices = [device]
        # for item in config['mapping']:
        #     devices.append(MiotSubSensor(device, item))
    except DeviceException as de:
        _LOGGER.warn(de)

        raise PlatformNotReady


    hass.data[DATA_KEY][host] = device
    # async_add_devices([device], update_before_add=True)
    async_add_devices(devices, update_before_add=True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

class MiotSensor(GenericMiotDevice):
    def __init__(self, device, config, device_info):
        GenericMiotDevice.__init__(self, device, config, device_info)
        self._state = None
        self._sensor_property = config.get(CONF_SENSOR_PROPERTY) or \
            list(config['mapping'].keys())[0]
        self._unit_of_measurement = config.get(CONF_SENSOR_UNIT)
        
    @property
    def state(self):
        """Return the state of the device."""
        return self._state
    
    async def async_update(self):
        await super().async_update()
        state = self._state_attrs
        if self._sensor_property is not None:
            self._state = state.get(self._sensor_property)
        else:
            try:
                self._state = state.get(self._mapping.keys()[0])
            except:
                self._state = None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

class MiotSubSensor(Entity):
    def __init__(self, parent_sensor, sensor_property):
        self._parent = parent_sensor
        self._sensor_property = sensor_property
    
    @property
    def state(self):
        """Return the state of the device."""
        _LOGGER.error(self._parent.device_state_attributes)
        try:
            return self._parent.device_state_attributes[self._sensor_property]
        except:
            return None
    
    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._parent.unique_id)},
            # 'name': self._name,
            # 'model': self._model,
            # 'manufacturer': (self._model or 'Xiaomi').split('.', 1)[0],
            # 'sw_version': self._state_attrs.get(ATTR_FIRMWARE_VERSION),
        }
    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._parent.unique_id}-{self._sensor_property}"

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return f"{self._parent.name} {self._sensor_property.capitalize()}"
