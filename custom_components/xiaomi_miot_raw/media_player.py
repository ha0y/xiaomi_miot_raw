from collections import OrderedDict
from datetime import timedelta
from functools import partial
from dataclasses import dataclass

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.components import media_player
from homeassistant.components.media_player import *
from homeassistant.components.media_player.const import *
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from miio.exceptions import DeviceException
from .deps.miio_new import MiotDevice
from homeassistant.components import persistent_notification

from . import GenericMiotDevice, ToggleableMiotDevice
from .deps.const import (ATTR_FIRMWARE_VERSION, ATTR_HARDWARE_VERSION,
                         ATTR_MODEL, ATTR_STATE_VALUE, CONF_CLOUD,
                         CONF_CONTROL_PARAMS, CONF_MAPPING, CONF_MODEL,
                         CONF_UPDATE_INSTANT, DOMAIN, MAP, SCHEMA)
import copy

TYPE = 'media_player'
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)

SCAN_INTERVAL = timedelta(seconds=10)

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
}


@dataclass
class dev_info:
    model             : str
    mac_address       : str
    firmware_version  : str
    hardware_version  : str

@asyncio.coroutine
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the fan from config."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)

    mappingnew = {}

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

        if 'a_l' not in mapping.keys():
            persistent_notification.async_create(
                hass,
                f"为了支持更多种类小爱，配置参数有变动，\n"
                f"请删除您的 **{config.get(CONF_NAME)}** 重新配置。谢谢\n",
                "Xiaomi MIoT")

        _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])

        try:
            if type(params) == OrderedDict:
                miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
            else:
                miio_device = MiotDevice(ip=host, token=token, mapping=mappingnew)
            device_info = dev_info(host,token,"","")
            device = MiotMediaPlayer(miio_device, config, device_info, hass, main_mi_type)
        except DeviceException as de:
            _LOGGER.warn(de)
            raise PlatformNotReady

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][f'{host}-{config.get(CONF_NAME)}'] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)

        @asyncio.coroutine
        def async_service_handler(service):
            """Map services to methods on XiaomiMiioDevice."""
            method = SERVICE_TO_METHOD.get(service.service)
            params = {
                key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
            }
            entity_ids = service.data.get(ATTR_ENTITY_ID)
            if entity_ids:
                devices = [
                    device
                    for device in hass.data[DOMAIN]['entities'].values()
                    if device.entity_id in entity_ids
                ]
            else:
                # devices = hass.data[DOMAIN]['entities'].values()
                _LOGGER.error("No entity_id specified.")

            update_tasks = []
            for device in devices:
                yield from getattr(device, method["method"])(**params)
                update_tasks.append(device.async_update_ha_state(True))

            if update_tasks:
                yield from asyncio.wait(update_tasks, loop=hass.loop)

        for service in SERVICE_TO_METHOD:
            schema = SERVICE_TO_METHOD[service].get("schema", SERVICE_SCHEMA)
            hass.services.async_register(
                DOMAIN, service, async_service_handler, schema=schema
            )

    else:
        _LOGGER.error("media player只能作为主设备！")
        pass

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    await async_setup_platform(hass, config, async_add_entities)


class MiotMediaPlayer(GenericMiotDevice, MediaPlayerEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        GenericMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)
        self._player_state = STATE_PAUSED
        self._sound_mode = ""
        self._device_class = DEVICE_CLASS_SPEAKER
        self._source = ""
        self._volume_level = 0.05

    @property
    def supported_features(self):
        """Return the supported features."""
        s = 0
        if 'a_l_play_control_play' in self._mapping:
            s |= SUPPORT_PLAY
        if 'a_l_play_control_pause' in self._mapping:
            s |= SUPPORT_PAUSE
        if 'a_l_play_control_next' in self._mapping:
            s |= SUPPORT_NEXT_TRACK
        if 'a_l_play_control_previous' in self._mapping:
            s |= SUPPORT_PREVIOUS_TRACK
        if self._did_prefix + 'mp_sound_mode' in self._mapping:
            s |= SUPPORT_SELECT_SOUND_MODE
        if 'mp_source' in self._ctrl_params:
            s |= SUPPORT_SELECT_SOURCE
        if self._did_prefix + 'volume' in self._mapping:
            s |= SUPPORT_VOLUME_SET
        # s |= SUPPORT_PLAY_MEDIA
        return s

    @property
    def state(self):
        """Return the state of the player."""
        return self._player_state

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        if s := self._ctrl_params.get('mp_sound_mode'):
            return list(s)
        return []

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available sources."""
        if s := self._ctrl_params.get('mp_source'):
            return list(s.keys())
        return []

    async def async_select_source(self, source):
        """Set the input source."""
        result = await self.call_action_new(*(self._ctrl_params['mp_source'][source].values()))
        if result:
            self._source = source
            self.schedule_update_ha_state()

    @property
    def device_class(self):
        """Return the device class of the media player."""
        return self._device_class

    async def async_media_play(self):
        """Send play command."""
        result = await self.call_action_new(*(self._mapping['a_l_play_control_play'].values()))
        if result:
            self._player_state = STATE_PLAYING
            self.schedule_update_ha_state()

    async def async_media_pause(self):
        """Send pause command."""
        result = await self.call_action_new(*(self._mapping['a_l_play_control_pause'].values()))
        if result:
            self._player_state = STATE_PAUSED
            self.schedule_update_ha_state()

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        result = await self.call_action_new(*(self._mapping[self._did_prefix + 'mp_sound_mode'].values()), [sound_mode])
        if result:
            # self._sound_mode = sound_mode
            self.schedule_update_ha_state()

    async def async_media_previous_track(self):
        """Send previous track command."""
        result = await self.call_action_new(*(self._mapping['a_l_play_control_previous'].values()))

    async def async_media_next_track(self):
        """Send next track command."""
        result = await self.call_action_new(*(self._mapping['a_l_play_control_next'].values()))

    async def async_set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        result = await self.set_property_new(self._did_prefix + "volume", self.convert_value(volume, 'volume', True, self._ctrl_params['volume']['value_range']))
        if result:
            self._volume_level = volume
            self.schedule_update_ha_state()

    async def async_speak_text(self, text):
        result = await self.call_action_new(*(self._mapping['a_l_intelligent_speaker_play_text'].values()), [text])

    async def async_execute_text(self, text, silent = False):
        result = await self.call_action_new(*(self._mapping['a_l_intelligent_speaker_execute_text_directive'].values()), [text, (0 if silent else 1)])

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume_level

    def _handle_platform_specific_attrs(self):
        super()._handle_platform_specific_attrs()
    #     player_state = self._state_attrs.get(self._did_prefix + 'playing_state')
    #     if player_state is not None and self._ctrl_params.get('playing_state'):
    #         if player_state == self._ctrl_params['playing_state'].get('paused'):
    #             self._player_state = STATE_PAUSED
    #         elif player_state == self._ctrl_params['playing_state'].get('playing'):
    #             self._player_state = STATE_PLAYING
    #         else:
    #             _LOGGER.warning(f"Unknown state for player {self._name}: {player_state}")

        self._volume_level = self.convert_value(
            self._state_attrs.get(self._did_prefix + 'volume') or 0,
            'volume', False, self._ctrl_params['volume']['value_range']
        )
