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
            self._mapping = user_input[CONF_MAPPING]
            self._params = user_input[CONF_CONTROL_PARAMS]
            
            device = MiioDevice(self._host, self._token)
            try:
                self._info = device.info()
            except DeviceException:
                errors['base'] = 'cannot_connect'
                
            if self._info is not None:
                unique_id = format_mac(self._info.mac_address)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                d = self._info.raw
                device_info = (
                    f"Model: {d['model']}\n"
                    f"Firmware: {d['fw_ver']}\n"
                    f"MAC: {d['mac']}\n"
                )
                                
            self._input2 = user_input
            return self.async_show_form(
            step_id="devinfo",
            data_schema=vol.Schema({
                vol.Required('devtype', default=''): vol.In(SUPPORTED_DOMAINS)
            }),
            description_placeholders={"device_info": device_info},
            errors=errors,
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=''): str,
                    vol.Required(CONF_HOST, default='192.168.'): str,
                    vol.Required(CONF_TOKEN, default=''): str,
                    vol.Required(CONF_MAPPING, default='{"switch_status":{"siid":2,"piid":1}}'): str,
                    vol.Required(CONF_CONTROL_PARAMS, default='{"switch_status":{"power_on":true,"power_off":false}}'): str,
                }
            ),
            # description_placeholders={"device_info": "device_info"},
            errors=errors,
        )
    
    async def async_step_devinfo(self, user_input=None):
        if user_input is not None:
            self._devtype = user_input['devtype']
            self._input2['devtype'] = self._devtype
            return self.async_create_entry(
                title=self._input2[CONF_NAME],
                data=self._input2,
            )
    
    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        return True