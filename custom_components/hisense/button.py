from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from .const import DOMAIN, device_suggested_object_id
from homeassistant.const import EntityCategory
import logging

_LOGGER = logging.getLogger(__name__)



async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]
    entities = [HisenseACUpdateButton(api[device_id], config_entry.entry_id) for device_id in api]
    async_add_entities(entities, True)
    entities = [HisenseACRefreshTokenButton(api[device_id], config_entry.entry_id) for device_id in api]
    async_add_entities(entities, True)


class HisenseACUpdateButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "force_update"

    def __init__(self, api, config_entry_id):
        self._api = api
        self._config_entry_id = config_entry_id
        self._attr_unique_id = f"{api.device_id}_force_update_button"
        self._attr_suggested_object_id = device_suggested_object_id(
            api.device_id, "force_update"
        )
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "translation_key": "hisense_ac",
            "manufacturer": "Hisense",
        }

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug(f"Button pressed for entity: {self._attr_unique_id}")
        await self._api.check_status()
        self.async_schedule_update_ha_state(True)


class HisenseACRefreshTokenButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "refresh_token"

    def __init__(self, api, config_entry_id):
        self._api = api
        self._config_entry_id = config_entry_id
        self._attr_unique_id = f"{api.device_id}_refresh_token"
        self._attr_suggested_object_id = device_suggested_object_id(
            api.device_id, "refresh_token"
        )
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._api.device_id)},
            "name": "Hisense AC",
            "translation_key": "hisense_ac",
            "manufacturer": "Hisense",
        }

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug(f"Button pressed for entity: {self._attr_unique_id}")
        await self._api.refresh()
