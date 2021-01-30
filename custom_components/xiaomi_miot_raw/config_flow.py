"""teset."""
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import *
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
)
import json
from homeassistant.helpers.device_registry import format_mac
from miio import (
    Device as MiioDevice,
    DeviceException,
)
from miio.miot_device import MiotDevice
import async_timeout
from aiohttp import ClientSession
from homeassistant.helpers import aiohttp_client, discovery
import requests
from .deps.miot_device_adapter import MiotAdapter

VALIDATE = {'fan': [{"switch_status", "speed"}, {"switch_status", "speed"}],
            'switch': [{"switch_status"}, {"switch_status"}],
            'light': [{"switch_status"}, {"switch_status"}],
            'cover': [{"motor_control"}, {"motor_control"}]
            }

async def validate_devinfo(hass, data):
    """检验配置是否缺项。无问题返回[[],[]]，有缺项返回缺项。"""
    # print(result)
    devtype = data['devtype']
    ret = [[],[]]
    requirements = VALIDATE.get(devtype)
    if not requirements:
        return ret
    else:
        for item in requirements[0]:
            if item not in json.loads(data[CONF_MAPPING]):
                ret[0].append(item)
        for item in requirements[1]:
            if item not in json.loads(data[CONF_CONTROL_PARAMS]):
                ret[1].append(item)
        return ret

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
        # print(data)
        # data = requests.get(url).json()
        print(data)
        for item in data:
            if item['device_model'] == model:
                return item
    return None

async def guess_mp_from_model(hass,model):
    cs = aiohttp_client.async_get_clientsession(hass)
    url_all = 'http://miot-spec.org/miot-spec-v2/instances?status=all'
    url_spec = 'http://miot-spec.org/miot-spec-v2/instance'
    dev_list = requests.get(url_all).json().get('instances')
    with async_timeout.timeout(10):
        try:
            dev_list = await cs.get(url_all).json().get('instances')
        except Exception:
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
                spec = await cs.get(url_spec, params=params).json()
            except Exception:
                spec = None
        if r:
            ad = MiotAdapter(spec)
            dt = ad.devtype
            mp = ad.get_mapping_by_snewid(dt)
            prm = ad.get_params_by_snewid(dt)
            return {
                'device_type': dt,
                'mapping': mp,
                'params': prm
            }
    else:
        return None
    # TODO
    
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

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        
        # Check if already configured
        # await self.async_set_unique_id(DOMAIN)
        # self._abort_if_unique_id_configured()

        if user_input is not None:
            
            self._name = user_input[CONF_NAME]
            self._host = user_input[CONF_HOST]
            self._token = user_input[CONF_TOKEN]
            # self._mapping = user_input[CONF_MAPPING]
            # self._params = user_input[CONF_CONTROL_PARAMS]
            
            device = MiioDevice(self._host, self._token)
            try:
                self._info = device.info()
            except DeviceException:
                # print("DeviceException!!!!!!")
                errors['base'] = 'cannot_connect'
            # except ValueError:
            #     errors['base'] = 'value_error'
                
                
            if self._info is not None:
                unique_id = format_mac(self._info.mac_address)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                d = self._info.raw
                self._model = d['model']
                device_info = (
                    f"Model: {d['model']}\n"
                    f"Firmware: {d['fw_ver']}\n"
                    f"MAC: {d['mac']}\n"
                )
            
                # self._info = self.get_devconfg_by_model(self._model)
                
                self._info = await async_get_mp_from_net(self.hass, self._model) \
                    or await guess_mp_from_model(self.hass, self._model)
                
                if self._info:
                    device_info += "\n已经自动发现配置参数。\n如无特殊需要，无需修改下列内容。\n"
                    devtype_default = self._info.get('device_type')
                    mapping_default = self._info.get('mapping')
                    params_default = self._info.get('params')
                else:
                    device_info += "请手动进行配置。\n"
                    devtype_default = ''
                    mapping_default = '{"switch_status":{"siid":2,"piid":1}}'
                    params_default = '{"switch_status":{"power_on":true,"power_off":false}}'

                self._input2 = user_input
                return self.async_show_form(
                    step_id="devinfo",
                    data_schema=vol.Schema({
                        vol.Required('devtype', default=devtype_default): vol.In(SUPPORTED_DOMAINS),
                        vol.Required(CONF_MAPPING, default=mapping_default): str,
                        vol.Required(CONF_CONTROL_PARAMS, default=params_default): str,
                        vol.Optional('cloud_read'): bool,
                        vol.Optional('cloud_write'): bool,
                        }),
                    description_placeholders={"device_info": device_info},
                    errors=errors,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST, default='192.168.'): str,
                    vol.Required(CONF_TOKEN): str,
                    # vol.Required(CONF_MAPPING, default='{"switch_status":{"siid":2,"piid":1}}'): str,
                    # vol.Required(CONF_CONTROL_PARAMS, default='{"switch_status":{"power_on":true,"power_off":false}}'): str,
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
            # self._input2['cloud_read'] = user_input['cloud_read']
            self._input2['cloud_write'] = user_input.get('cloud_write')
            
            v = await validate_devinfo(self.hass, self._input2)
            if v == [[],[]] :
            
                try:
                    device = MiotDevice(ip=self._input2[CONF_HOST], token=self._input2[CONF_TOKEN], mapping=json.loads(self._input2[CONF_MAPPING]))
                    result = device.get_properties_for_mapping()
                    # print(result)
                    if not user_input.get('cloud_read') and not user_input.get('cloud_write'):
                        return self.async_create_entry(
                            title=self._input2[CONF_NAME],
                            data=self._input2,
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
                except DeviceException:
                    # errors["base"] = "cannot_connect"
                    # hint = "请检查 mapping 中的各项 iid 是否正确。如果进行到此步才出现错误，有可能是它们导致的。"
                    pass
            else:
                errors["base"] = "bad_params"
                
                hint = ""
                if v[0]:
                    hint += "\nmapping 缺少必须配置的项目："
                    for item in v[0]:
                        hint += (item + ', ')
                if v[1]:
                    hint += "\nparams 缺少必须配置的项目："
                    for item in v[1]:
                        hint += (item + ', ')
            
            # if info:
        return self.async_show_form(
            step_id="devinfo",
            data_schema=vol.Schema({
                vol.Required('devtype', default=user_input['devtype']): vol.In(SUPPORTED_DOMAINS),
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
    # def get_devconfg_by_model(self, model):
    #     print(model)
    #     dev = json.loads(TEST)
    #     for item in dev:
    #         if item['device_model'] == model:
    #             return item
    #     return None
    
    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        return True
