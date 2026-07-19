from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    ac_coordinators = [
        c for c in coordinators.values() if c.device_type == "空调"
    ]
    entities = [AcScreenSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)
    entities = [AuxHeatSwitch(coordinator) for coordinator in ac_coordinators]
    async_add_entities(entities)


class AcScreenSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "screen_panel"

    def __init__(self, coordinator):
        super().__init__(coordinator, "screen", "screen")
        self._attr_icon = "mdi:clock-digital"

    @property
    def is_on(self):
        return self.status.get("screen_on", True)

    async def async_turn_on(self):
        _LOGGER.debug(f"Turning on screen for {self._attr_unique_id}")
        if await self.client.send_logic_command(41, 1):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC screen")

    async def async_turn_off(self):
        _LOGGER.debug(f"Turning off screen for {self._attr_unique_id}")
        if await self.client.send_logic_command(41, 0):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC screen")


class AuxHeatSwitch(HisenseEntity, SwitchEntity):
    _attr_translation_key = "auxiliary_heat"

    def __init__(self, coordinator):
        super().__init__(coordinator, "aux_heat", "aux_heat")
        self._attr_icon = "mdi:heating-coil"

    @property
    def is_on(self):
        return self.status.get("aux_heat", False)

    async def async_turn_on(self):
        if await self.client.send_logic_command(28, 1):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn on Hisense AC auxiliary heat")

    async def async_turn_off(self):
        if await self.client.send_logic_command(28, 0):
            self.coordinator.async_update_from_client()
            return
        raise HomeAssistantError("Failed to turn off Hisense AC auxiliary heat")
