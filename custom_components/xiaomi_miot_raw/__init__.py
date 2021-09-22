import asyncio
import json
import time
import logging
from datetime import timedelta
from functools import partial
from dataclasses import dataclass

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientSession
from distutils.version import StrictVersion
from homeassistant.const import *
from homeassistant.const import __version__ as current_version
from homeassistant.core import callback
from homeassistant.components import persistent_notification
from homeassistant.exceptions import PlatformNotReady, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, discovery
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.util import color
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice
import copy
import math
from collections import OrderedDict

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
    SERVICE_SCHEMA,
    SERVICE_TO_METHOD,
    MAP,
    DUMMY_IP,
    DUMMY_TOKEN,
)

from .deps.xiaomi_cloud_new import *
from .deps.xiaomi_cloud_new import MiCloud
from .deps.miot_coordinator import MiotCloudCoordinator
from asyncio.exceptions import CancelledError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_TOKEN): cv.string,
                vol.Required(CONF_MAPPING): vol.All(),
                vol.Required(CONF_CONTROL_PARAMS): vol.All(),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
HAVE_NUMBER = True if StrictVersion(current_version.replace(".dev","a")) >= StrictVersion("2020.12") else False
HAVE_SELECT = True if StrictVersion(current_version.replace(".dev","a")) >= StrictVersion("2021.7") else False

async def async_setup(hass, hassconfig):
    """Setup Component."""
    hass.data.setdefault(DOMAIN, {})

    config = hassconfig.get(DOMAIN) or {}
    hass.data[DOMAIN]['config'] = config
    hass.data[DOMAIN].setdefault('entities', {})
    hass.data[DOMAIN].setdefault('configs', {})
    hass.data[DOMAIN].setdefault('miot_main_entity', {})
    hass.data[DOMAIN].setdefault('micloud_devices', [])
    hass.data[DOMAIN].setdefault('cloud_instance_list', [])
    hass.data[DOMAIN].setdefault('event_fetcher_list', [])
    hass.data[DOMAIN].setdefault('add_handler', {})

    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    hass.data[DOMAIN]['component'] = component

    await component.async_setup(config)
    return True

async def async_setup_entry(hass, entry):
    """Set up shopping list from config flow."""
    hass.data.setdefault(DOMAIN, {})

    # entry for MiCloud login
    if 'username' in entry.data:
        return await _setup_micloud_entry(hass, entry)

    config = {}
    for item in [CONF_NAME,
                 CONF_HOST,
                 CONF_TOKEN,
                 CONF_CLOUD,
                 'cloud_write',
                 'devtype',
                 'ett_id_migrated',
                 'cloud_device_info',
                 ]:
        config[item] = entry.data.get(item)
    for item in [CONF_MAPPING,
                 CONF_CONTROL_PARAMS,
                 ]:
        config[item] = json.loads(entry.data.get(item))

    if type(entry.data.get('devtype')) == str:
        persistent_notification.async_create(
                            hass,
                            f"感谢您选择本插件！\n"
                            f"本插件最近的更新，支持了“一个设备多个类型”的配置方式，\n"
                            f"您的 **{entry.data.get(CONF_NAME)}** 配置项是旧版本格式。\n"
                            f"建议您重新添加设备，确认设备正常后删除旧设备，\n"
                            f"即可消除此提示。\n",
                            "Xiaomi MIoT")
        config[CONF_MAPPING] = {entry.data.get('devtype'): config[CONF_MAPPING]}
        config[CONF_CONTROL_PARAMS] = {entry.data.get('devtype'): config[CONF_CONTROL_PARAMS]}

    config['config_entry'] = entry
    entry_id = entry.entry_id
    unique_id = entry.unique_id
    hass.data[DOMAIN]['configs'][entry_id] = config
    hass.data[DOMAIN]['configs'][unique_id] = config

    if type(entry.data.get('devtype')) == str:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, entry.data.get('devtype')))
    else:
        devtype_new = entry.data.get('devtype')
        if 'number' not in devtype_new:
            devtype_new += ['number']
        if 'select' not in devtype_new:
            devtype_new += ['select']
        if 'sensor' in devtype_new and 'binary_sensor' not in devtype_new:
            devtype_new += ['binary_sensor']
        for t in devtype_new:
            if t == 'number' and not HAVE_NUMBER:
                continue
            if t == 'select' and not HAVE_SELECT:
                continue
            hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, t))

    return True

async def async_unload_entry(hass, entry):
    if 'username' in entry.data:
        # TODO
        try:
            hass.data[DOMAIN]['micloud_devices'] = []
            for item in hass.data[DOMAIN]['cloud_instance_list']:
                if item['username'] == entry.data['username']:
                    del item
                    return True
            return False
        except Exception as ex:
            _LOGGER.error(ex)
            return False
    else:
        entry_id = entry.entry_id
        unique_id = entry.unique_id
        hass.data[DOMAIN]['configs'].pop(entry_id)
        if unique_id:
            hass.data[DOMAIN]['configs'].pop(unique_id)
        if type(entry.data.get('devtype')) == str:
            hass.async_create_task(hass.config_entries.async_forward_entry_unload(entry, entry.data.get('devtype')))
        else:
            for t in entry.data.get('devtype'):
                hass.async_create_task(hass.config_entries.async_forward_entry_unload(entry, t))

        return True

async def async_remove_entry(hass, entry):
    if 'username' in entry.data:
        remove_ok = all(
            await asyncio.gather(
                *[
                    hass.config_entries.async_remove(v['config_entry'].entry_id)
                    for v in hass.data[DOMAIN]['configs'].values() if v['config_entry'].source == 'batch_add'
                ]
            )
        )
        return remove_ok
    return True

async def _setup_micloud_entry(hass, config_entry):
    """Thanks to @AlexxIT """
    data: dict = config_entry.data.copy()
    server_location = data.get('server_location') or 'cn'

    session = aiohttp_client.async_create_clientsession(hass, auto_cleanup=False)
    cloud = MiCloud(session)
    cloud.svr = server_location

    if 'service_token' in data:
        # load devices with saved MiCloud auth
        cloud.auth = data
        devices = await cloud.get_total_devices([server_location])
    else:
        devices = None

    if devices is None:
        _LOGGER.debug(f"Login to MiCloud for {config_entry.title}")
        login_result = await cloud.login(data['username'], data['password'])
        if login_result == (0, None):
            # update MiCloud auth in .storage
            data.update(cloud.auth)
            hass.config_entries.async_update_entry(config_entry, data=data)

            devices = await cloud.get_total_devices([server_location])

            if devices is None:
                _LOGGER.error("Can't load devices from MiCloud")
        elif login_result[0] == -2:
            _LOGGER.error(f"Internal error occurred while logging in Xiaomi account: {login_result[1]}")
            raise ConfigEntryNotReady(login_result[1])
        else:
            _LOGGER.error("Can't login to MiCloud")
            raise ConfigEntryNotReady
    if userid := cloud.auth.get('user_id'):
        # TODO don't allow login the same account twice
        hass.data[DOMAIN]['cloud_instance_list'].append({
            "user_id": userid,
            "username": data['username'],
            "cloud_instance": cloud,
            "coordinator": MiotCloudCoordinator(hass, cloud)
        })

    # load devices from or save to .storage
    filename = sanitize_filename(data['username'])
    store = Store(hass, 1, f"{DOMAIN}/{filename}.json")
    if devices is None:
        _LOGGER.debug("Loading a list of devices from the .storage")
        devices = await store.async_load()
    else:
        _LOGGER.debug(f"Loaded from MiCloud {len(devices)} devices")
        await store.async_save(devices)

    if devices is None:
        _LOGGER.debug("No devices in .storage")
        return False

    # TODO: Think about a bunch of devices
    if 'micloud_devices' not in hass.data[DOMAIN]:
        hass.data[DOMAIN]['micloud_devices'] = devices
    else:
        hass.data[DOMAIN]['micloud_devices'] += devices

    return True

def sanitize_filename(s: str):
    valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ','_')
    return filename

@dataclass
class dev_info:
    model             : str
    mac_address       : str     # Not available for cloud
    firmware_version  : str
    hardware_version  : str     # Not available for cloud


async def async_generic_setup_platform(
    hass,
    config,
    async_add_devices,
    discovery_info,
    TYPE,           # 每个设备类型调用此函数时指定自己的类型，因此函数执行中只处理这个类型的设备
    main_class_dict : dict,
    sub_class_dict : dict = {},
    *,
    special_dict={}
):
    DATA_KEY = TYPE + '.' + DOMAIN
    hass.data.setdefault(DATA_KEY, {})

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)
    if params is None: params = OrderedDict()

    id = config['config_entry'].entry_id if 'config_entry' in config else None
    # if id is None, then it is from YAML.
    if TYPE == 'sensor' and 'event_based' in params:
        di = config.get('cloud_device_info')
        device_info = dev_info(
            di['model'],
            di['mac'],
            di['fw_version'],
            ""
        )

        sensor_devices = [main_class_dict['_event_based_sensor'](None, config, device_info, hass, item) for item in mapping.items()]
        if id is not None:
            hass.data[DOMAIN]['miot_main_entity'][id] = sensor_devices[0]
        async_add_devices(sensor_devices, update_before_add=True)
        return True

    if 'ir' in params:
        # TYPE number and select will also come here
        if TYPE == 'light':
            device = main_class_dict['_ir_light'](config, hass, 'ir_light_control')
        elif TYPE == 'media_player':
            device = main_class_dict['_ir_tv'](config, hass, 'ir_tv_control')
        elif TYPE == 'climate':
            device = main_class_dict['_ir_aircon'](config, hass, 'ir_aircondition_control')
        else:
            return False
        _LOGGER.info(f"Initializing InfraRed device {config.get(CONF_NAME)}, type: {TYPE}")
        if id is not None:
            hass.data[DOMAIN]['miot_main_entity'][id] = device
        async_add_devices([device], update_before_add=False)
        return True

    mappingnew = {}
    paramsnew = {}

    main_mi_type = None
    other_mi_type = []

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
        if TYPE == 'sensor':
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
                raise ConfigEntryNotReady(de) from None
            else:
                if not (di := config.get('cloud_device_info')):
                    _LOGGER.error(f"未能获取到设备信息，请删除 {config.get(CONF_NAME)} 重新配置。")
                    raise ConfigEntryNotReady from None
                else:
                    device_info = dev_info(
                        di['model'],
                        di['mac'],
                        di['fw_version'],
                        "N/A for Cloud Mode"
                    )
        except OSError as oe:
            raise ConfigEntryNotReady(oe) from None

        if TYPE in ('sensor', 'binary_sensor'):
            """Begin special policy for sensor"""
            device = main_class_dict['_sensor'](miio_device, config, device_info, hass, main_mi_type)
            sensor_devices = [device]
            binary_devices = []
            _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
            if id is not None:
                hass.data[DOMAIN]['miot_main_entity'][id] = device
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
                        sensor_devices.append(sub_class_dict['_sub_sensor'](
                            device, mappingnew, paramsnew, main_mi_type,
                            {'sensor_property': k, "sensor_unit": unit}
                        ))
                    else:
                        binary_devices.append(sub_class_dict['_sub_binary_sensor'](
                            device, mappingnew, paramsnew, main_mi_type,
                            {'sensor_property': k}
                        ))
            async_add_devices(sensor_devices, update_before_add=True)
            if binary_devices:
                retry_time = 1
                while True:
                    if 'binary_sensor' in hass.data[DOMAIN]['add_handler']:
                        if id in hass.data[DOMAIN]['add_handler']['binary_sensor']:
                            break
                    retry_time *= 2
                    if retry_time > 120:
                        _LOGGER.error(f"Cannot create binary sensor for {config.get(CONF_NAME)}({host}) !")
                        raise PlatformNotReady
                    else:
                        _LOGGER.debug(f"Waiting for binary sensor of {config.get(CONF_NAME)}({host}) ({retry_time - 1} seconds).")
                        await asyncio.sleep(retry_time)

                hass.data[DOMAIN]['add_handler']['binary_sensor'][id](binary_devices, update_before_add=True)
        else:
            """Begin normal policy"""
            if main_mi_type in main_class_dict:
                device = main_class_dict[main_mi_type](miio_device, config, device_info, hass, main_mi_type)
            else:
                device = main_class_dict['default'](miio_device, config, device_info, hass, main_mi_type)

            _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
            if id is not None:
                hass.data[DOMAIN]['miot_main_entity'][id] = device
            hass.data[DOMAIN]['entities'][device.unique_id] = device
            async_add_devices([device], update_before_add=True)

    elif not sub_class_dict:
        _LOGGER.error(f"{TYPE}只能作为主设备！请检查{config.get(CONF_NAME)}配置")

    if TYPE in ('sensor', 'binary_sensor'):
        if other_mi_type:
            retry_time = 1
            while True:
                if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(id):
                    if isinstance(parent_device, main_class_dict['_sensor']):
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
                if k in paramsnew and HAVE_NUMBER:
                    if isinstance(paramsnew[k], dict):
                        if 'access' in v and 'value_range' in v:
                            if v['access'] >> 1 & 0b01:
                                continue
                if k in paramsnew and HAVE_SELECT:
                    if isinstance(paramsnew[k], dict):
                        if 'access' in v and 'value_list' in v:
                            if v['access'] >> 1 & 0b01:
                                continue
                sensor_devices.append(sub_class_dict['_sub_sensor'](parent_device, mappingnew, paramsnew, other_mi_type[0],{'sensor_property': k}))

            # device = MiotSubSensor(parent_device, "switch_switch_status")
            async_add_devices(sensor_devices, update_before_add=True)
        return
    if sub_class_dict and id is not None:
        retry_time = 1
        while True:
            if parent_device := hass.data[DOMAIN]['miot_main_entity'].get(id):
                break
            else:
                retry_time *= 2
                if retry_time > 30:
                    _LOGGER.error(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after 30 seconds!")
                    raise PlatformNotReady
                else:
                    _LOGGER.debug(f"The main device of {config.get(CONF_NAME)}({host}) is still not ready after {retry_time - 1} seconds.")
                    await asyncio.sleep(retry_time)

        for k,v in mapping.items():
            if k in MAP[TYPE]:
                for kk,vv in v.items():
                    mappingnew[f"{k[:10]}_{kk}"] = vv

        devices = []

        for item in other_mi_type:
            if item == "indicator_light":
                if not params[item].get('enabled'):
                    continue
            if item == "a_l" and TYPE == 'fan' and HAVE_SELECT:
                continue

            if item in sub_class_dict:
                devices.append(sub_class_dict[item](parent_device, mapping.get(item), params.get(item), item))
            else:
                devices.append(sub_class_dict['default'](parent_device, mapping.get(item), params.get(item), item))

        async_add_devices(devices, update_before_add=True)


