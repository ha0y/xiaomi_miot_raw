import json
import re

import async_timeout
import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from aiohttp import ClientSession
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.const import *
from homeassistant.helpers import aiohttp_client, discovery
from homeassistant.helpers.device_registry import format_mac
from homeassistant.core import callback
from miio import Device as MiioDevice
from miio import DeviceException
from miio.miot_device import MiotDevice

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
    SUPPORTED_DOMAINS,
    DEFAULT_NAME,
    DUMMY_IP,
    DUMMY_TOKEN,
    MAP,
)
from .deps.miot_device_adapter import MiotAdapter
from .deps.special_devices import SPECIAL_DEVICES
from .deps.xiaomi_cloud_new import MiCloud


async def async_get_mp_from_net(hass, model):
    cs = aiohttp_client.async_get_clientsession(hass)
    url = "https://raw.githubusercontent.com/ha0y/miot-params/master/main.json"
    with async_timeout.timeout(10):
        try:
            a = await cs.get(url)
        except Exception:
            a = None
    if a:
        data = await a.json(content_type=None)
        for item in data:
            if item['device_model'] == model:
                return item
    return None

async def guess_mp_from_model(hass,model):
    if m := SPECIAL_DEVICES.get(model):
        return {
            "device_type": m["device_type"],
            "mapping": json.dumps(m["mapping"],separators=(',', ':')),
            "params": json.dumps(m["params"],separators=(',', ':')),
        }

    cs = aiohttp_client.async_get_clientsession(hass)
    url_all = 'http://miot-spec.org/miot-spec-v2/instances?status=all'
    url_spec = 'http://miot-spec.org/miot-spec-v2/instance'
    with async_timeout.timeout(10):
        try:
            a = await cs.get(url_all)

        except Exception:
            a = None
    if a:
        dev_list = await a.json(content_type=None)
        dev_list = dev_list.get('instances')
    else:
        dev_list = None
    result = None
    if dev_list:
        for item in dev_list:
            if model == item['model']:
                result = item
        urn = result['type']
        params = {'type': urn}
        with async_timeout.timeout(10):
            try:
                s = await cs.get(url_spec, params=params)
            except Exception:
                s = None
        if s:
            spec = await s.json()
            ad = MiotAdapter(spec)

            mp = ad.get_all_mapping()
            prm = ad.get_all_params()
            dt = ad.get_all_devtype() # 这一行必须在下面
            return {
                'device_type': dt or ['switch'],
                'mapping': json.dumps(mp,separators=(',', ':')),
                'params': json.dumps(prm,separators=(',', ':'))
            }
    else:
        return {
            'device_type': [],
            'mapping': "{}",
            'params': "{}"
        }
    # TODO

def data_masking(s: str, n: int) -> str:
    return re.sub(f"(?<=.{{{n}}}).(?=.{{{n}}})", "*", str(s))

def get_conn_type(device: dict):
    #0 for wifi, 1 for zigbee, 2 for BLE, 3 for Mesh, -1 for Unknown
    if 'blt' in device['did']:
        return 2
    if device.get('parent_id'):
        return 1
    if device.get('localip'):
        if not device.get('ssid'):
            return 3
        return 0
    return -1


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow"""
        self._name = vol.UNDEFINED
        self._host = vol.UNDEFINED
        self._token = vol.UNDEFINED
        self._mapping = vol.UNDEFINED
        self._params = vol.UNDEFINED
        self._devtype = vol.UNDEFINED
        self._info = None
        self._model = None
        self._did = None
        self._cloud_device = None
        self._input2 = {}
        self._input2.update({"ett_id_migrated": True}) # 新的实体ID格式，相对稳定，为避免已有ID变化，灰度选项
        self._actions = {
            'xiaomi_account': "登录小米账号",
            'localinfo': "接入设备"
        }

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            if user_input['action'] == 'xiaomi_account':
                return await self.async_step_xiaomi_account()
            elif user_input['action'] == 'localinfo':
                return await self.async_step_localinfo()
            else:
                device = next(d for d in self.hass.data[DOMAIN]['micloud_devices']
                              if d['did'] == user_input['action'])
                self._cloud_device = device
                self._model = device.get('model')
                self._did = device.get('did')
                if get_conn_type(device) == 0:
                    return await self.async_step_localinfo({
                        CONF_NAME: device.get('name') or DEFAULT_NAME,
                        CONF_HOST: device.get('localip') or DUMMY_IP,
                        CONF_TOKEN: device.get('token') if device.get('localip') else DUMMY_TOKEN,
                    })
                else:
                    return await self.async_step_localinfo({
                        CONF_NAME: device.get('name') or DEFAULT_NAME,
                        CONF_HOST: DUMMY_IP,
                        CONF_TOKEN: DUMMY_TOKEN,
                    })

        if DOMAIN in self.hass.data and 'micloud_devices' in self.hass.data[DOMAIN]:
            for device in self.hass.data[DOMAIN]['micloud_devices']:
                if device['did'] not in self._actions:
                    dt = get_conn_type(device)
                    dt = "WiFi" if dt == 0 else "ZigBee" if dt == 1 else "BLE" if dt == 2 \
                                           else "BLE Mesh" if dt == 3 else "Unknown"
                    name = f"接入 {device['name']} ({dt}{', '+device['localip'] if (dt == '''WiFi''') else ''})"
                    self._actions[device['did']] = name
            self._actions.pop('xiaomi_account')

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('action', default='localinfo'): vol.In(self._actions),
            })
        )

    async def async_step_localinfo(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        # Check if already configured
        # await self.async_set_unique_id(DOMAIN)
        # self._abort_if_unique_id_configured()

        if user_input is not None:

            self._name = user_input[CONF_NAME]
            self._host = user_input[CONF_HOST]
            self._token = user_input[CONF_TOKEN]
            self._input2 = {**self._input2, **user_input}

            device = MiioDevice(self._host, self._token)
            try:
                self._info = device.info()
            except DeviceException:
                errors['base'] = 'cannot_connect'
            # except ValueError:
            #     errors['base'] = 'value_error'

            if self._info is not None:
                unique_id = format_mac(self._info.mac_address)
                # await self.async_set_unique_id(unique_id)
                for entry in self._async_current_entries():
                    if entry.unique_id == unique_id:
                        persistent_notification.async_create(
                            self.hass,
                            f"您新添加的设备: **{self._name}** ，\n"
                            f"其 MAC 地址与现有的某个设备相同。\n"
                            f"只是通知，不会造成任何影响。",
                            "设备可能重复")
                        break

                self._abort_if_unique_id_configured()
                d = self._info.raw
                self._model = d['model']
                device_info = (
                    f"Model: {d['model']}\n"
                    f"Firmware: {d['fw_ver']}\n"
                    f"MAC: {d['mac']}\n"
                )

                self._info = await guess_mp_from_model(self.hass, self._model)

                if self._info and self._info.get('mapping') != "{}":
                    device_info += "\n已经自动发现配置参数。\n如无特殊需要，无需修改下列内容。\n"
                    devtype_default = self._info.get('device_type')

                    mp = self._info.get('mapping')
                    prm = self._info.get('params')
                    mapping_default = mp
                    params_default = prm
                else:
                    device_info += f"很抱歉，未能自动发现配置参数。但这不代表您的设备不受支持。\n您可以[手工编写配置](https://github.com/ha0y/xiaomi_miot_raw/#文件配置法)，或者将型号 **{self._model}** 报告给作者。"
                    devtype_default = ['switch']
                    mapping_default = '{"switch":{"switch_status":{"siid":2,"piid":1}}}'
                    params_default = '{"switch":{"switch_status":{"power_on":true,"power_off":false}}}'

                return self.async_show_form(
                    step_id="devinfo",
                    data_schema=vol.Schema({
                        vol.Required('devtype', default=devtype_default): cv.multi_select(SUPPORTED_DOMAINS),
                        vol.Required(CONF_MAPPING, default=mapping_default): str,
                        vol.Required(CONF_CONTROL_PARAMS, default=params_default): str,
                        vol.Optional('cloud_read'): bool,
                        vol.Optional('cloud_write'): bool,
                        }),
                    description_placeholders={"device_info": device_info},
                    errors=errors,
                )
            else:
                return await self.async_step_xiaoai({
                    CONF_MODEL: self._model
                } if self._model else None)

        return self.async_show_form(
            step_id="localinfo",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST, default='192.168.'): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            # description_placeholders={"device_info": "device_info"},
            errors=errors,
        )

    async def async_step_devinfo(self, user_input=None):
        errors = {}
        hint = ""
        if user_input is not None:
            self._devtype = user_input['devtype']
            self._input2['devtype'] = self._devtype
            self._input2[CONF_MAPPING] = user_input[CONF_MAPPING]
            self._input2[CONF_CONTROL_PARAMS] = user_input[CONF_CONTROL_PARAMS]
            self._input2['cloud_write'] = user_input.get('cloud_write')

            try:
                # print(result)
                if not user_input.get('cloud_read') and not user_input.get('cloud_write'):
                    device = MiotDevice(ip=self._input2[CONF_HOST], token=self._input2[CONF_TOKEN], mapping=list(json.loads(self._input2[CONF_MAPPING]).values())[0])
                    result = device.get_properties_for_mapping()
                    return self.async_create_entry(
                        title=self._input2[CONF_NAME],
                        data=self._input2,
                    )
                else:
                    if cloud := self.hass.data[DOMAIN].get('cloud_instance'):
                        if not self._did:
                            for dev in self.hass.data[DOMAIN]['micloud_devices']:
                                if dev.get('localip') == self._input2[CONF_HOST]:
                                    self._did = dev['did']
                        if self._did:
                            self._input2['update_from_cloud'] = {
                                'did': self._did,
                                'userId': cloud.auth['user_id'],
                                'serviceToken': cloud.auth['service_token'],
                                'ssecurity': cloud.auth['ssecurity'],
                            }
                            self._input2['cloud_device_info'] = {
                                'name': self._cloud_device.get('name'),
                                'mac': self._cloud_device.get('mac'),
                                'did': self._cloud_device.get('did'),
                                'model': self._cloud_device.get('model'),
                                'fw_version': self._cloud_device['extra'].get('fw_version'),
                            }
                            return self.async_create_entry(
                                title=self._input2[CONF_NAME],
                                data=self._input2,
                            )
                        else:
                            return self.async_show_form(
                                step_id="cloudinfo",
                                data_schema=vol.Schema({
                                    vol.Required('did'): str,
                                    vol.Required('userId', default=cloud.auth['user_id']): str,
                                    vol.Required('serviceToken', default=cloud.auth['service_token']): str,
                                    vol.Required('ssecurity', default=cloud.auth['ssecurity']): str,
                                }),
                            description_placeholders={"device_info": "没找到 did，请手动填一下"},
                            errors=errors,
                        )
                    else:
                        return self.async_show_form(
                            step_id="cloudinfo",
                            data_schema=vol.Schema({
                                vol.Required('did'): str,
                                vol.Required('userId'): str,
                                vol.Required('serviceToken'): str,
                                vol.Required('ssecurity'): str,
                                }),
                            # description_placeholders={"device_info": hint},
                            errors=errors,
                        )
            except DeviceException as ex:
                errors["base"] = "no_local_access"
                hint = f"错误信息: {ex}"

        return self.async_show_form(
            step_id="devinfo",
            data_schema=vol.Schema({
                vol.Required('devtype', default=user_input['devtype']): cv.multi_select(SUPPORTED_DOMAINS),
                vol.Required(CONF_MAPPING, default=user_input[CONF_MAPPING]): str,
                vol.Required(CONF_CONTROL_PARAMS, default=user_input[CONF_CONTROL_PARAMS]): str,
                vol.Optional('cloud_read'): bool,
                vol.Optional('cloud_write'): bool,
                }),
            description_placeholders={"device_info": hint},
            errors=errors,
        )

    async def async_step_cloudinfo(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._input2['update_from_cloud'] = {}
            self._input2['update_from_cloud']['did'] = user_input['did']
            self._input2['update_from_cloud']['userId'] = user_input['userId']
            self._input2['update_from_cloud']['serviceToken'] = user_input['serviceToken']
            self._input2['update_from_cloud']['ssecurity'] = user_input['ssecurity']

            return self.async_create_entry(
                title=self._input2[CONF_NAME],
                data=self._input2,
            )

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        return True

    async def async_step_xiaomi_account(self, user_input=None, error=None):
        if user_input:
            # if not user_input['servers']:
                # return await self.async_step_xiaomi_account(error='no_servers')

            session = aiohttp_client.async_create_clientsession(self.hass)
            cloud = MiCloud(session)
            if await cloud.login(user_input['username'],
                                 user_input['password']):
                user_input.update(cloud.auth)
                return self.async_create_entry(title=data_masking(user_input['username'], 4),
                                               data=user_input)

            else:
                return await self.async_step_xiaomi_account(error='cant_login')

        return self.async_show_form(
            step_id='xiaomi_account',
            data_schema=vol.Schema({
                vol.Required('username'): str,
                vol.Required('password'): str,
                # vol.Required('servers', default=['cn']):
                    # cv.multi_select(SERVERS)
            }),
            errors={'base': error} if error else None
        )

    async def async_step_xiaoai(self, user_input=None, error=None):
        errors = {}
        if user_input is not None:
            self._input2 = {**self._input2, **user_input}
            self._model = user_input[CONF_MODEL]
            # Line 240-270
            self._info = await guess_mp_from_model(self.hass, self._model)
            hint = ""
            if self._info and self._info.get('mapping') != "{}":
                hint += "\n根据您手动输入的 model，已经自动发现配置参数。\n如无特殊需要，无需修改下列内容。\n"
                devtype_default = self._info.get('device_type')

                mp = self._info.get('mapping')
                prm = self._info.get('params')
                mapping_default = mp
                params_default = prm
            else:
                hint += f"很抱歉，未能自动发现配置参数。但这不代表您的设备不受支持。\n您可以[手工编写配置](https://github.com/ha0y/xiaomi_miot_raw/#文件配置法)，或者将型号 **{self._model}** 报告给作者。"
                devtype_default = []
                mapping_default = '{"switch":{"switch_status":{"siid":2,"piid":1}}}'
                params_default = '{"switch":{"switch_status":{"power_on":true,"power_off":false}}}'


            return self.async_show_form(
                step_id="devinfo",
                data_schema=vol.Schema({
                    vol.Required('devtype', default=devtype_default): cv.multi_select(SUPPORTED_DOMAINS),
                    vol.Required(CONF_MAPPING, default=mapping_default): str,
                    vol.Required(CONF_CONTROL_PARAMS, default=params_default): str,
                    vol.Optional('cloud_read'): bool,
                    vol.Optional('cloud_write'): bool,
                }),
                description_placeholders={"device_info": hint},
                errors=errors,
            )

        return self.async_show_form(
            step_id='xiaoai',
            data_schema=vol.Schema({
                vol.Required(CONF_MODEL, default=self._model): str,
            }),
            errors={'base': 'no_connect_warning'}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for tado."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self._input2 = config_entry.data.copy()
        self._steps = []

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if 'password' in self._input2:
            return self.async_abort(reason="no_configurable_account")
        if self._input2['devtype'] == ['sensor']:
            self._steps.append(self.async_step_sensor())
        if 'climate' in self._input2['devtype']:
            self._steps.append(self.async_step_climate())

        if self._steps:
            self._steps.append(self.async_finish())
            return await self._steps[0]
        else:
            return self.async_abort(reason="no_configurable_options")

    async def async_step_sensor(self, user_input=None):
        if user_input is not None:
            prm = json.loads(self._input2[CONF_CONTROL_PARAMS])
            for device,p in prm.items():
                if device in MAP['sensor']:
                    p.update(user_input)
            self._input2[CONF_CONTROL_PARAMS] = json.dumps(prm,separators=(',', ':'))
            self._steps.pop(0)
            return await self._steps[0]

        d = False
        for device,p in json.loads(self._input2[CONF_CONTROL_PARAMS]).items():
            if device in MAP['sensor'] and p.get('show_individual_sensor'):
                d = True
                break
        return self.async_show_form(
            step_id='sensor',
            data_schema=vol.Schema({
                vol.Optional('show_individual_sensor', default=d): bool,
            }),
        )

    async def async_step_climate(self, user_input=None):
        if user_input is not None:
            prm = json.loads(self._input2[CONF_CONTROL_PARAMS])
            for device,p in prm.items():
                if device in MAP['climate']:
                    p.update(user_input)
            self._input2[CONF_CONTROL_PARAMS] = json.dumps(prm,separators=(',', ':'))
            self._steps.pop(0)
            return await self._steps[0]

        return self.async_show_form(
            step_id='climate',
            data_schema=vol.Schema({
                vol.Optional('current_temp_source', default=""): str,
            }),
        )

    async def async_finish(self):
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=self._input2
        )
        await self.hass.config_entries.async_reload(
            self.config_entry.entry_id
        )
        return self.async_create_entry(title="", data=None)