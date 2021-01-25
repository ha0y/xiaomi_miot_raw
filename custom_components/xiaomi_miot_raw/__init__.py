import asyncio
import logging
from functools import partial
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.entity import (
    Entity,
    ToggleEntity,
)
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from aiohttp import ClientSession
import async_timeout
from homeassistant.helpers import aiohttp_client
from .deps.xiaomi_cloud import *
import json

_LOGGER = logging.getLogger(__name__)

CONF_UPDATE_INSTANT = "update_instant"
CONF_MAPPING = 'mapping'
CONF_CONTROL_PARAMS = 'params'
CONF_CLOUD = 'update_from_cloud'

ATTR_STATE_VALUE = "state_value"
ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

class GenericMiotDevice(Entity):
    """通用 MiOT 设备"""

    def __init__(self, device, config, device_info, hass = None):
        """Initialize the entity."""
        self._device = device
        self._mapping = config.get(CONF_MAPPING)
        self._ctrl_params = config.get(CONF_CONTROL_PARAMS)

        self._name = config.get(CONF_NAME)
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False

        self._model = device_info.model
        self._unique_id = "{}-{}-{}".format(
            device_info.model, device_info.mac_address, self._name
        )
        # self._icon = "mdi:flask-outline"
        
        self._hass = hass
        self._cloud = config.get(CONF_CLOUD)

        self._available = None
        self._state = None
        self._assumed_state = False
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
            # ATTR_STATE_PROPERTY: self._state_property,
        }

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    # @property
    # def icon(self):
    #     """Return the icon to use for device if any."""
    #     return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_job(partial(func, *args, **kwargs))

            _LOGGER.info("Response received from %s: %s", self._name, result)
            if result[0]['code'] == 0:
                return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_update(self):
        """Fetch state from the device."""
        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False or self._skip_update:
            self._skip_update = False
            return

        try:
            if not self._cloud:
                response = await self.hass.async_add_job(
                        self._device.get_properties_for_mapping
                    )
                self._available = True

                statedict={}
                count4004 = 0
                for r in response:
                    if r['code'] == 0:
                        try:
                            f = self._ctrl_params[r['did']]['value_ratio']
                            statedict[r['did']] = round(r['value'] * f , 3)
                        except KeyError:
                            statedict[r['did']] = r['value']
                    else:
                        statedict[r['did']] = None
                        if r['code'] == -4004:
                            count4004 += 1
                        else:
                            _LOGGER.error("Error getting %s 's property '%s' (code: %s)", self._name, r['did'], r['code'])
                if count4004 == len(response):
                    self._assumed_state = True
                    self._skip_update = True
                    # _LOGGER.warn("设备不支持状态反馈")

            else:
                with async_timeout.timeout(10):
                    a = await self.async_update_from_mijia(
                        aiohttp_client.async_get_clientsession(self._hass),
                        self._cloud.get("userId"),
                        self._cloud.get("serviceToken"),
                        self._cloud.get("ssecurity"),
                        self._cloud.get("did"),
                    )
                dict1 = {}
                statedict = {}
                if a:
                    for item in a['result']:
                        if dict1.get(item['siid']):
                            dict1[item['siid']][item['piid']] = item.get('value')
                        else:
                            dict1[item['siid']] = {}
                            dict1[item['siid']][item['piid']] = item.get('value')

                    for key, value in self._mapping.items():
                        try:
                            statedict[key] = dict1[value['siid']][value['piid']]
                        except KeyError:
                            statedict[key] = None
                            
                else:
                    pass
                
            if statedict.get('brightness'):
                statedict['brightness_'] = statedict.pop('brightness')
            if statedict.get('speed'):
                statedict['speed_'] = statedict.pop('speed')
            self._state_attrs.update(statedict)


        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching %s 's state: %s", self._name, ex)
    
    async def async_update_from_mijia(self, session: ClientSession, userId: str, serviceToken: str, ssecurity: str, did: str):
        api_base = "https://api.io.mi.com/app"
        url = "/miotspec/prop/get"

        data1 = {}
        data1['datasource'] = 1
        data1['params'] = []
        for value in self._mapping.values():
            data1['params'].append({**{'did':did},**value})
        data2 = json.dumps(data1,separators=(',', ':'))
        
        nonce = gen_nonce()
        signed_nonce = gen_signed_nonce(ssecurity, nonce)
        signature = gen_signature(url, signed_nonce, nonce, data2)
        payload = {
            'signature': signature,
            '_nonce': nonce,
            'data': data2
        }
        headers = {
            'content-type': "application/x-www-form-urlencoded",
            'x-xiaomi-protocal-flag-cli': "PROTOCAL-HTTP2",
            'connection': "Keep-Alive",
            'accept-encoding': "gzip",
            'cache-control': "no-cache",
            'cookie': f'userId={userId};serviceToken={serviceToken}'
        }
        resp = await session.post(api_base+url, data=payload, headers=headers)
        data = await resp.json(content_type=None)
        _LOGGER.info("Response of %s from cloud: %s", self._name, data)
        if data['code'] == 0:
            self._available = True
            return data
        else:
            if data['message'] == "auth err":
                _LOGGER.error(f"{self._name} 的小米账号登录态失效，请重新登录")
            else:
                _LOGGER.error(f"Failed updating states from Mijia, code: {data['code']}, message: {data['message']}")
            self._available = False
            return None


class ToggleableMiotDevice(GenericMiotDevice, ToggleEntity):
    def __init__(self, device, config, device_info, hass = None):
        GenericMiotDevice.__init__(self, device, config, device_info, hass)
        
        
    async def async_turn_on(self, **kwargs):
        """Turn on."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.set_property,
            "switch_status",
            self._ctrl_params['switch_status']['power_on'],
        )
        if result:
            self._state = True


    async def async_turn_off(self, **kwargs):
        """Turn off."""
        result = await self._try_command(
            "Turning the miio device off failed.",
            self._device.set_property,
            "switch_status",
            self._ctrl_params['switch_status']['power_off'],
        )

        if result:
            self._state = False

    async def async_update(self):

        await super().async_update()
        state = self._state_attrs['switch_status']
        _LOGGER.debug("%s 's new state: %s", self._name, state)

        if state == self._ctrl_params['switch_status']['power_on']:
            self._state = True
        elif state == self._ctrl_params['switch_status']['power_off']:
            self._state = False
        elif not self.assumed_state:
            _LOGGER.warning(
                "New state (%s) of %s doesn't match expected values: %s/%s",
                state, self._name,
                self._ctrl_params['switch_status']['power_on'],
                self._ctrl_params['switch_status']['power_off'],
            )
            _LOGGER.warning(type(self._ctrl_params['switch_status']['power_on']))
            _LOGGER.warning(type(state))
            self._state = None

        self._state_attrs.update({ATTR_STATE_VALUE: state})

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return self._assumed_state

    @property
    def state(self):
        return STATE_ON if self._state else STATE_OFF

    @property
    def is_on(self):
        return self._state

