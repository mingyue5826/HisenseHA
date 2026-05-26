"""Shared entity helpers for the Hisense integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, device_suggested_object_id
from .coordinator import HisenseDataUpdateCoordinator
from .pyhisenseapi import HiSenseAC


class HisenseEntity(CoordinatorEntity[HisenseDataUpdateCoordinator]):
    """Base entity for one Hisense AC device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HisenseDataUpdateCoordinator,
        unique_suffix: str,
        object_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.device_id}_{unique_suffix}"
        self._attr_suggested_object_id = device_suggested_object_id(
            coordinator.client.device_id,
            object_suffix,
        )

    @property
    def client(self) -> HiSenseAC:
        """Return the device API client."""
        return self.coordinator.client

    @property
    def status(self) -> dict[str, Any]:
        """Return the latest coordinated status."""
        return self.coordinator.data or self.client.get_status()

    @property
    def device_info(self):
        """Return Home Assistant device registry info."""
        return {
            "identifiers": {(DOMAIN, self.client.device_id)},
            "name": "Hisense AC",
            "translation_key": "hisense_ac",
            "manufacturer": "Hisense",
        }
