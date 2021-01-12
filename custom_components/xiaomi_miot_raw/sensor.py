import asyncio
import logging
from collections import defaultdict
from functools import partial
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice 
from . import GenericMiotDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT sensor"
DATA_KEY = "sensor.xiaomi_miot_raw"
DOMAIN = "xiaomi_miot_raw"

CONF_SENSOR_PROPERTY = "sensor_property"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_DEFAULT_PROPERTIES = "default_properties"
CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SENSOR_PROPERTY): cv.string,
        vol.Optional(CONF_SENSOR_UNIT): cv.string,
        vol.Required(CONF_MAPPING):vol.All(),
        vol.Optional(CONF_CONTROL_PARAMS):vol.All(),
    }
)

ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"
ATTR_PROPERTIES = "properties"
ATTR_SENSOR_PROPERTY = "sensor_property"
ATTR_METHOD = "method"
ATTR_PARAMS = "params"

# SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

# SERVICE_SCHEMA_SET_PROPERTIES = SERVICE_SCHEMA.extend(
#     {
#         vol.Optional(ATTR_PROPERTIES, default=["power"]): vol.All(
#             cv.ensure_list, [cv.string]
#         )
#     }
# )

# SERVICE_SCHEMA_COMMAND = SERVICE_SCHEMA.extend(
#     {
#         vol.Required(ATTR_METHOD): cv.string,
#         vol.Optional(ATTR_PARAMS, default=[]): vol.All(cv.ensure_list),
#     }
# )

# SERVICE_CUSTOM_TURN_ON = "sensor_turn_on"
# SERVICE_CUSTOM_TURN_OFF = "sensor_turn_off"
# SERVICE_SET_PROPERTIES = "sensor_set_properties"
# SERVICE_COMMAND = "sensor_raw_command"

# SERVICE_TO_METHOD = {
#     SERVICE_CUSTOM_TURN_ON: {"method": "async_turn_on"},
#     SERVICE_CUSTOM_TURN_OFF: {"method": "async_turn_off"},
#     SERVICE_SET_PROPERTIES: {
#         "method": "async_set_properties",
#         "schema": SERVICE_SCHEMA_SET_PROPERTIES,
#     },
#     SERVICE_COMMAND: {"method": "async_command", "schema": SERVICE_SCHEMA_COMMAND},
# }


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])


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
    except DeviceException as de:
        _LOGGER.warn(de)

        raise PlatformNotReady


    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)

    # @asyncio.coroutine
    # def async_service_handler(service):
    #     """Map services to methods on XiaomiMiioDevice."""
    #     method = SERVICE_TO_METHOD.get(service.service)
    #     params = {
    #         key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
    #     }
    #     entity_ids = service.data.get(ATTR_ENTITY_ID)
    #     if entity_ids:
    #         devices = [
    #             device
    #             for device in hass.data[DATA_KEY].values()
    #             if device.entity_id in entity_ids
    #         ]
    #     else:
    #         devices = hass.data[DATA_KEY].values()

    #     update_tasks = []
    #     for device in devices:
    #         yield from getattr(device, method["method"])(**params)
    #         update_tasks.append(device.async_update_ha_state(True))

    #     if update_tasks:
    #         yield from asyncio.wait(update_tasks, loop=hass.loop)

    # for service in SERVICE_TO_METHOD:
    #     schema = SERVICE_TO_METHOD[service].get("schema", SERVICE_SCHEMA)
    #     hass.services.async_register(
    #         DOMAIN, service, async_service_handler, schema=schema
    #     )
class MiotSensor(GenericMiotDevice):
    def __init__(self, device, config, device_info):
        GenericMiotDevice.__init__(self, device, config, device_info)
        self._state = None
        
    @property
    def state(self):
        """Return the state of the device."""
        return self._state
    
    def update(self):
        super().async_update()
        state = self._state_attrs
        if self._sensor_property is not None:
            self._state = state.get(self._sensor_property)
        #     pass
        # else:
        #     try:
        #         device_info = await self.hass.async_add_job(self._device.info)
        #         self._state = device_info.accesspoint.get("rssi", self._model)

        #     except DeviceException as ex:
        #         self._available = False
        #         _LOGGER.error("Got exception while fetching device info: %s", ex)

