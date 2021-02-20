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

from datetime import timedelta
from . import GenericMiotDevice, MiotSubDevice, get_dev_info, dev_info
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
    UNIT_MAPPING,
)
from collections import OrderedDict
TYPE = 'sensor'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

CONF_SENSOR_PROPERTY = "sensor_property"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_DEFAULT_PROPERTIES = "default_properties"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

ATTR_PROPERTIES = "properties"
ATTR_SENSOR_PROPERTY = "sensor_property"
SCAN_INTERVAL = timedelta(seconds=5)
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
    if params is None: params = OrderedDict()

    mappingnew = {}
    paramsnew = {}

    main_mi_type = None
    other_mi_type = []

    #sensor的添加逻辑和其他实体不一样。他会把每个属性都作为实体。其他设备会作为attr

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
        device = MiotSensor(miio_device, config, device_info, hass, main_mi_type)

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][host] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    if other_mi_type:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(host):
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
        for k,v in params.items():
            if k in MAP[TYPE]:
                for kk,vv in v.items():
                    paramsnew[f"{k[:10]}_{kk}"] = vv
        devices = []
        for k in mappingnew.keys():
            devices.append(MiotSubSensor(parent_device, mappingnew, paramsnew, other_mi_type[0],{'sensor_property': k}))

        # device = MiotSubSensor(parent_device, "switch_switch_status")
        async_add_devices(devices, update_before_add=True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data))
    await async_setup_platform(hass, config, async_add_entities)

async def async_unload_entry(hass, config_entry, async_add_entities):
    return True

class MiotSensor(GenericMiotDevice):
    def __init__(self, device, config, device_info, hass = None, mi_type = None):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, mi_type)
        self._state = None
        self._sensor_property = config.get(CONF_SENSOR_PROPERTY)
        self._unit_of_measurement = config.get(CONF_SENSOR_UNIT)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_update(self):
        if self._update_instant is False or self._skip_update:
            self._skip_update = False
            return
        await super().async_update()
        state = self._state_attrs
        if self._sensor_property is not None:
            self._state = state.get(self._sensor_property)
        else:
            try:
                self._state = state.get(list(self._mapping.keys())[0])
            except Exception as ex:
                _LOGGER.error(ex)
                self._state = None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

class MiotSubSensor(MiotSubDevice):
    def __init__(self, parent_device, mapping, params, mitype, others={}):
        super().__init__(parent_device, mapping, params, mitype)
        self._sensor_property = others.get('sensor_property')
        self.entity_id = f"{DOMAIN}.{parent_device._entity_id}-{others.get('sensor_property').split('_')[-1]}"
        try:
            self._unit_of_measurement = UNIT_MAPPING[params[self._sensor_property]['unit']]
        except:
            self._unit_of_measurement = None

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return self._parent_device.device_state_attributes[self._sensor_property]
        except:
            return None

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._parent_device.unique_id)},
            # 'name': self._name,
            # 'model': self._model,
            # 'manufacturer': (self._model or 'Xiaomi').split('.', 1)[0],
            # 'sw_version': self._state_attrs.get(ATTR_FIRMWARE_VERSION),
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement


    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._parent_device.unique_id}-{self._sensor_property}"

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return f"{self._parent_device.name} {self._sensor_property.replace('_', ' ').capitalize()}"
