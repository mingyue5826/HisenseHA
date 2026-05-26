"""Data update coordinator for Hisense AC devices."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .pyhisenseapi import HiSenseAC

import logging

_LOGGER = logging.getLogger(__name__)


class HisenseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a single Hisense AC device."""

    def __init__(self, hass: HomeAssistant, client: HiSenseAC) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.device_id}",
            update_interval=None,
        )

    async def _async_setup(self) -> None:
        """Refresh the cloud access token before the first status fetch."""
        try:
            refreshed = await self.client.refresh()
        except Exception as err:
            raise UpdateFailed("Failed to refresh Hisense access token") from err
        if refreshed:
            return
        raise UpdateFailed("Failed to refresh Hisense access token")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh state from the Hisense cloud."""
        try:
            status = await self.client.check_status()
        except Exception as err:
            raise UpdateFailed("Failed to fetch Hisense AC status") from err
        if not status:
            raise UpdateFailed("Failed to fetch Hisense AC status")
        return status

    def async_update_from_client(self) -> None:
        """Push the client's cached status into Home Assistant listeners."""
        self.async_set_updated_data(self.client.get_status())
