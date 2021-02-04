import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import *

CONF_UPDATE_INSTANT = "update_instant"
CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'
CONF_CLOUD = 'update_from_cloud'
CONF_MODEL = 'model'
CONF_SENSOR_PROPERTY = "sensor_property"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_DEFAULT_PROPERTIES = "default_properties"

ATTR_STATE_VALUE = "state_value"
ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

DOMAIN = 'xiaomi_miot_raw'
SUPPORTED_DOMAINS = [
    "sensor",
    "switch",
    "light",
    "fan",
    "cover",
    "humidifier",
]
DEFAULT_NAME = "Xiaomi MIoT Device"
SCHEMA = {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UPDATE_INSTANT, default=True): cv.boolean,
        vol.Optional(CONF_CLOUD): vol.All(),
        vol.Optional('cloud_write'):vol.All(),

        vol.Required(CONF_MAPPING):vol.All(),
        vol.Optional(CONF_CONTROL_PARAMS):vol.All(),

        vol.Optional(CONF_SENSOR_PROPERTY): cv.string,
        vol.Optional(CONF_SENSOR_UNIT): cv.string,
}
MAP = {
    "sensor": {
        "air_monitor",
        "water_purifier",
        "cooker",
        "pressure_cooker",
        "induction_cooker",
        "power_consumption",
        "electricity",
        "environment",
    },
    "switch": {
        "switch",
        "outlet",
    },
    "light": {
        "light",
    },
    "fan": {
        "fan",
        "ceiling_fan",
        "air_fresh",
        "air_purifier",
    },
    "cover": {
        "curtain",
        "airer",

    },
    "humidifier": {
        "humidifier",
        "dehumidifier",
    },
}