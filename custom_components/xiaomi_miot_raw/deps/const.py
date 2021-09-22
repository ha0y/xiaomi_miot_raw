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
    "media_player",
    "climate",
    "lock",
    "water_heater",
    "vacuum",
    "binary_sensor",
]
DEFAULT_NAME = "Xiaomi MIoT Device"

DUMMY_IP = "255.255.255.255"
DUMMY_TOKEN = "00000000000000000000000000000000"

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

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SERVICE_TO_METHOD = {
    'speak_text': {
        "method": "async_speak_text",
        "schema": SERVICE_SCHEMA.extend({
                vol.Required('text'): cv.string,
            })
    },
    'execute_text': {
        "method": "async_execute_text",
        "schema": SERVICE_SCHEMA.extend({
                vol.Required('text'): cv.string,
                vol.Optional('silent'): cv.boolean,
            })
    },
    'call_action': {
        "method": "call_action_new",
        "schema": SERVICE_SCHEMA.extend({
                vol.Required('siid'): vol.All(),
                vol.Required('aiid'): vol.All(),
                vol.Optional('inn'): vol.All(),
            })
    },
    'set_miot_property': {
        "method": "set_property_for_service",
        "schema": SERVICE_SCHEMA.extend({
                vol.Required('siid'): vol.All(),
                vol.Required('piid'): vol.All(),
                vol.Required('value'): vol.All(),
            })
    },
}

MAP = {
    "sensor": {
        "air_fryer",
        "air_monitor",
        "battery",
        "bed",
        "chair",
        "chair_customize",
        "coffee_machine",
        "cooker",
        "door",
        "doorbell",
        "fridge",
        "electricity",
        "environment",
        "filter",
        "filter_2",
        "filter_3",
        "filter_4",
        "filter_5",
        "filter_6",
        "filter_7",
        "filter_8",
        "gas_sensor",
        "health_pot",
        "illumination_sensor",
        "induction_cooker",
        "juicer",
        "magnet_sensor",
        "microwave_oven",
        "motion_detection",
        "motion_sensor",
        "multifunction_cooking_pot",
        "oven",
        "plant_monitor",
        "power_consumption",
        "power_10A_consumption",
        "pressure_cooker",
        "printer",
        "remain_clean_time",
        "repellent",
        "repellent_liquid",
        "router",
        "sleep_info",
        "sleep_monitor",
        "submersion_sensor",
        "tds_sensor",
        "temperature_humidity_sensor",
        "walking_pad",
        "water_purifier",
    },
    "switch": {
        "switch",
        "outlet",
        "switch_2",
        "switch_3",
        "switch_4",
        "switch_5",
        "switch_6",
        "switch_7",
        "switch_8",
        "switch_usb",
        "coffee_machine",
        "fish_tank",
    },
    "light": {
        "light",
        "light_2",
        "light_3",
        "light_4",
        "light_5",
        "light_6",
        "light_7",
        "light_8",
        "ambient_light",
        "ambient_light_custom",
        "germicidal_lamp",
        "plant_light",
        "indicator_light",
        "night_light",
        "screen",
    },
    "fan": {
        "a_l",
        "fan",
        "ceiling_fan",
        "air_fresh",
        "air_purifier",
        "washer",
        "hood",
        "fan_control",
        "dryer",
        "toilet",
        "settings",
        "settings_2",
        "air_fresh_heater",
        "bed",
        "pet_drinking_fountain",
        "mosquito_dispeller",
    },
    "cover": {
        "curtain",
        "airer",
        "window_opener",
    },
    "humidifier": {
        "humidifier",
        "dehumidifier",
    },
    "media_player": {
        "media_player",
        "speaker",
        "play_control",
        "television",
    },
    "climate": {
        "air_conditioner",
        "air_condition_outlet",
        "heater",
        "ir_aircondition_control",
        "thermostat",
    },
    "lock": {
        "physical_controls_locked",
    },
    "water_heater": {
        "water_heater",
        "kettle",
        "dishwasher",
        "water_dispenser",
    },
    "vacuum": {
        "vacuum",
    },
    "binary_sensor": {},
    "select": {"a_l"},
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
