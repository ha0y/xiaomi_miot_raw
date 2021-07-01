import asyncio
import logging
from collections import defaultdict
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ENTITY_ID, CONF_HOST, CONF_NAME,
                                 CONF_TOKEN)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import aiohttp_client, discovery
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice
from .deps.xiaomi_cloud_new import MiCloud

from datetime import timedelta
from . import GenericMiotDevice, MiotSubDevice, dev_info
from .binary_sensor import MiotSubBinarySensor
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
from .deps.ble_event_parser import (
    EventParser,
    BleDoorParser,
    BleLockParser,
    TimestampParser,
    ZgbIlluminationParser,
)
from collections import OrderedDict
from .deps.miot_coordinator import MiotEventCoordinator
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

DEVCLASS_MAPPING = {
    "battery"         : ["battery"],
    "humidity"        : ["humidity"],
    "illuminance"     : ["illuminance"],
    "signal_strength" : ["signal_strength"],
    "temperature"     : ["temperature"],
    "timestamp"       : ["timestamp"],
    "power"           : ["electric_power"],
    "pressure"        : ["pressure"],
    "current"         : ["electric_current"],
    "energy"          : ["power_consumption"],
    "power_factor"    : ["power_factor"],
    "voltage"         : ["voltage"],
    "carbon_dioxide"  : ["co2_density"],
}
# pylint: disable=unused-argument
@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""
    hass.data.setdefault(DATA_KEY, {})
    hass.data[DOMAIN]['add_handler'].setdefault(TYPE, {})
    if 'config_entry' in config:
        id = f"{config.get(CONF_HOST)}-{config.get(CONF_NAME)}"
        hass.data[DOMAIN]['add_handler'][TYPE].setdefault(id, async_add_devices)

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)
    if params is None: params = OrderedDict()

    if 'event_based' in params:
        di = config.get('cloud_device_info')
        device_info = dev_info(
            di['model'],
            di['mac'],
            di['fw_version'],
            ""
        )
        sensor_devices = [MiotEventBasedSensor(None, config, device_info, hass, item) for item in mapping.items()]
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = sensor_devices[0]
        # device = MiotEventBasedSensor(None, config, device_info, hass, params['eb_type'])
        # devices = [device]
        # _LOGGER.info(f"{params['eb_type']} is the main device of {host}.")
        # hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        # hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices(sensor_devices, update_before_add=True)
        return True

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
        for k,v in params.items():
            if k in MAP[TYPE]:
                for kk,vv in v.items():
                    paramsnew[f"{k[:10]}_{kk}"] = vv
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
        sensor_devices = [device]
        binary_devices = []
        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        if main_mi_type:
            for k in mappingnew.keys():
                if 'a_l_' in k:
                    continue
                if k in paramsnew:
                    unit = paramsnew[k].get('unit')
                    format_ = paramsnew[k].get('format')
                else:
                    unit = format_ = None
                if format_ != 'bool':
                    sensor_devices.append(MiotSubSensor(
                        device, mappingnew, paramsnew, main_mi_type,
                        {'sensor_property': k, CONF_SENSOR_UNIT: unit}
                    ))
                else:
                    binary_devices.append(MiotSubBinarySensor(
                        device, mappingnew, paramsnew, main_mi_type,
                        {'sensor_property': k}
                    ))
        async_add_devices(sensor_devices, update_before_add=True)
        if binary_devices:
            retry_time = 1
            while True:
                if 'binary_sensor' in hass.data[DOMAIN]['add_handler']:
                    if f"{host}-{config.get(CONF_NAME)}" in hass.data[DOMAIN]['add_handler']['binary_sensor']:
                        break
                retry_time *= 2
                if retry_time > 120:
                    _LOGGER.error(f"Cannot create binary sensor for {config.get(CONF_NAME)}({host}) !")
                    raise PlatformNotReady
                else:
                    _LOGGER.debug(f"Waiting for binary sensor of {config.get(CONF_NAME)}({host}) ({retry_time - 1} seconds).")
                    await asyncio.sleep(retry_time)

            hass.data[DOMAIN]['add_handler']['binary_sensor'][f"{host}-{config.get(CONF_NAME)}"](binary_devices, update_before_add=True)

    if other_mi_type:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(f'{host}-{config.get(CONF_NAME)}'):
                if isinstance(parent_device, MiotSensor):
                    return
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
        sensor_devices = []
        for k in mappingnew.keys():
            sensor_devices.append(MiotSubSensor(parent_device, mappingnew, paramsnew, other_mi_type[0],{'sensor_property': k}))

        # device = MiotSubSensor(parent_device, "switch_switch_status")
        async_add_devices(sensor_devices, update_before_add=True)


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

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
        state = self._state_attrs
        if self._sensor_property is not None:
            self._state = state.get(self._sensor_property)
        else:
            try:
                self._state = state.get(list(self._mapping.keys())[0])
            except Exception as ex:
                _LOGGER.error(ex)
                self._state = None

class MiotSubSensor(MiotSubDevice):
    def __init__(self, parent_device, mapping, params, mitype, others={}):
        super().__init__(parent_device, mapping, params, mitype)
        self._sensor_property = others.get('sensor_property')
        self._name_suffix = self._sensor_property.replace('_', ' ').capitalize()
        if self._sensor_property in params:
            if params[self._sensor_property].get('name'):
                self._name_suffix = params[self._sensor_property]['name']
        self.entity_id = f"{DOMAIN}.{parent_device._entity_id}-{others.get('sensor_property').split('_')[-1]}"
        try:
            if u := others.get(CONF_SENSOR_UNIT):
                self._unit_of_measurement = UNIT_MAPPING.get(u) or u
            else:
                self._unit_of_measurement = UNIT_MAPPING.get(params[self._sensor_property]['unit']) or params[self._sensor_property]['unit']
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
    def device_class(self):
        """Return the device class of the sensor."""
        try:
            return next(k for k,v in DEVCLASS_MAPPING.items() for item in v if item in self._sensor_property)
        except StopIteration:
            return None

    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._parent_device.unique_id}-{self._sensor_property}"

class MiotEventBasedSensor(Entity):
    def __init__(self, device, config, device_info, hass = None, event_item = None):
        """event_item 形如: {'motion':{'key':1, 'type':'prop'}}"""
        def setup_cloud_event(self, hass) -> tuple:
            try:
                mc = next(cloud['cloud_instance'] for cloud in hass.data[DOMAIN]['cloud_instance_list']
                    if cloud['user_id'] == self._cloud.get('userId'))
            except StopIteration:
                _LOGGER.info(f"Setting up xiaomi account for {self._name}...")
                mc = MiCloud(
                    aiohttp_client.async_get_clientsession(self._hass)
                )
                mc.login_by_credientals(
                    self._cloud.get('userId'),
                    self._cloud.get('serviceToken'),
                    self._cloud.get('ssecurity')
                )

            co = MiotEventCoordinator(hass, mc, self._cloud, self._event_item)
            # hass.data[DOMAIN]['cloud_instance_list'].append({
            #     "user_id": self._cloud.get('userId'),
            #     "username": None,  # 不是从UI配置的用户，没有用户名
            #     "cloud_instance": mc,
            #     "coordinator": co
            # })
            return (mc, co)


        self._ctrl_params = config.get(CONF_CONTROL_PARAMS) or {}
        self._event_item = event_item
        self._name = config.get(CONF_NAME)

        self._model = device_info.model
        self._host = config.get(CONF_HOST)
        self._unique_id = f"{device_info.model.split('.')[-1]}-event-{config.get(CONF_CLOUD)['did'][-6:]}-{self._event_item[0]}"
        self._device_identifier = f"{device_info.model.split('.')[-1]}-event-{config.get(CONF_CLOUD)['did'][-6:]}"
        if config.get('ett_id_migrated'):
            self._entity_id = self._unique_id
            self.entity_id = f"{DOMAIN}.{self._entity_id}"
        else:
            self._entity_id = None

        self._hass = hass
        self._cloud = config.get(CONF_CLOUD)

        self._cloud_instance = None
        self.coordinator = None
        if self._cloud:
            c = setup_cloud_event(self, hass)
            self._cloud_instance = c[0]
            self.coordinator = c[1]
        self._available = True
        self._state = None
        self._response_data = {}
        self._assumed_state = False
        self._state_attrs = {
            ATTR_MODEL: self._model,
        }
        self._last_notified = 0
        self._callbacks = set()
        self.logs = []

        self.create_sub_entities()

    @property
    def should_poll(self):
        """Poll the miio device."""
        return False

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return f"{self._name} {self._event_item[0]}"

    # @property
    # def icon(self):
    #     """Return the icon to use for device if any."""
    #     return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state attributes of the device."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data[0][0]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def device_info(self):
        return {
            'identifiers': {(DOMAIN, self._device_identifier)},
            'name': self._name,
            'model': self._model,
            'manufacturer': (self._model or 'Xiaomi').split('.', 1)[0].capitalize(),
            'sw_version': self._state_attrs.get(ATTR_FIRMWARE_VERSION),
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        statedict = self.coordinator.data
        self.logs = statedict

        self._state_attrs = {
            ATTR_MODEL: self._model,
        }
        if statedict:
            self._state_attrs.update(statedict)
        self.async_write_ha_state()
        self.publish_updates()

    def register_callback(self, callback):
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    def create_sub_entities(self):
        k = list(self._event_item)[1]['key']
        ett_to_add = []
        if k == 'device_log':
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'last_triggered',
                    'name': '上次触发',
                    'data_processor': TimestampParser,
                    'property': 'friendly_time',
                    'icon': 'mdi:history',
                })
            )
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'illumination',
                    'name': 'Illumination',
                    'data_processor': ZgbIlluminationParser,
                    'property': 'illumination',
                    'icon': 'mdi:white-balance-sunny',
                })
            )
        elif k == 7:
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'door_status',
                    'name': '门状态',
                    'data_processor': BleDoorParser,
                    'property': 'event_name',
                    'icon': 'mdi:door-closed',
                })
            )
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'door_time',
                    'name': '门状态时间',
                    'data_processor': BleDoorParser,
                    'property': 'friendly_time',
                    'icon': 'mdi:timeline-clock-outline',
                })
            )
        elif k == 11:
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'lock_action',
                    'name': '锁状态',
                    'data_processor': BleLockParser,
                    'property': 'action_name',
                    'icon': 'mdi:lock-question',
                })
            )
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'lock_method',
                    'name': '开锁方式',
                    'data_processor': BleLockParser,
                    'property': 'method_name',
                    'icon': 'mdi:key-wireless',
                })
            )
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'lock_time',
                    'name': '锁状态时间',
                    'data_processor': BleLockParser,
                    'property': 'friendly_time',
                    'icon': 'mdi:lock-clock',
                })
            )
            ett_to_add.append(
                MiotEventBasedSubSensor(self, {
                    'id': 'lock_operator_id',
                    'name': '操作者ID',
                    'data_processor': BleLockParser,
                    'property': 'key_id_short',
                    'icon': 'mdi:account-key',
                })
            )

        self._hass.data[DOMAIN]['add_handler']['sensor'][f"{self._host}-{self._name}"](ett_to_add, update_before_add=True)

class MiotEventBasedSubSensor(Entity):
    def __init__(self, parent_sensor, options):
        self._parent_sensor = parent_sensor
        self._options = options
        self._id = self._options.get('id')
        self._data_processor = self._options.get('data_processor')
        self._property = self._options.get('property')
        self._name = self._options.get('name')
        self._icon = self._options.get('icon')
        self._model = parent_sensor._model
        self._state_attrs = {}

        self._unique_id = f'{parent_sensor.unique_id}-{self._id}'
        self._entity_id = f"{parent_sensor._entity_id}-{self._id}"
        self.entity_id = f"{DOMAIN}.{self._entity_id}"

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return f"{self._parent_sensor._name} {self._name}"

    @property
    def should_poll(self):
        """Poll the miio device."""
        return False

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def state(self):
        """Return the state attributes of the device."""
        if self._parent_sensor.logs:
            dt = self._parent_sensor.logs[0][1]
            return getattr(self._data_processor(dt), self._property)
        else:
            return None

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def device_info(self):
        return self._parent_sensor.device_info

    async def async_added_to_hass(self):
        self._parent_sensor.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self._parent_sensor.remove_callback(self.async_write_ha_state)
