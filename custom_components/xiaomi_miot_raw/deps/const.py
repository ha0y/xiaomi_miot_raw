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
    "media_player"
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
        vol.Required(CONF_CONTROL_PARAMS):vol.All(),

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
        "switch_2",
        "switch_3",
        "switch_4",
    },
    "light": {
        "light",
        "light_2",
        "light_3",
        "light_4",
    },
    "fan": {
        "a_l",
        "fan",
        "ceiling_fan",
        "air_fresh",
        "air_purifier",
        "washer",
    },
    "cover": {
        "curtain",
        "airer",
    },
    "humidifier": {
        "humidifier",
        "dehumidifier",
    },
    "media_player": {
        "media_player",
        "speaker",
        "play_control",
    },
}

UNIT_MAPPING = {
    "percentage" : PERCENTAGE                                , # 百分比
    "celsius"    : TEMP_CELSIUS                              , # 摄氏度
    "seconds"    : "秒"                                      , # 秒
    "minutes"    : "分钟"                                    , # 分
    "hours"      : "小时"                                    , # 小时
    "days"       : "天"                                      , # 天
    "kelvin"     : TEMP_KELVIN                               , # 开氏温标
    "pascal"     : "Pa"                                      , # 帕斯卡(大气压强单位)
    "arcdegrees" : "rad"                                     , # 弧度(角度单位)
    "rgb"        : "RGB"                                     , # RGB(颜色)
    "watt"       : POWER_WATT                                , # 瓦特(功率)
    "litre"      : VOLUME_LITERS                             , # 升
    "ppm"        : CONCENTRATION_PARTS_PER_MILLION           , # ppm浓度
    "lux"        : LIGHT_LUX                                 , # 勒克斯(照度)
    "mg/m3"      : CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER  , # 毫克每立方米
}