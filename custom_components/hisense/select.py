"""Disabled refrigerator mode entities pending validated API mappings."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity

WORK_MODE_OPTIONS = ["智能", "速冷", "自定义"]
VARIATION_MODE_OPTIONS = ["母婴", "0℃养鲜", "原鲜", "除菌"]

FRIDGE_SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="work_mode_select",
        translation_key="work_mode_select",
        options=WORK_MODE_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:settings",
        entity_registry_enabled_default=False,
    ),
    SelectEntityDescription(
        key="variation_mode_select",
        translation_key="variation_mode_select",
        options=VARIATION_MODE_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:box-variant",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    fridge_coordinators = [
        c for c in coordinators.values() if c.device_type == "冰箱"
    ]

    entities = [
        HisenseFridgeModeSelect(coordinator, desc)
        for coordinator in fridge_coordinators
        for desc in FRIDGE_SELECT_DESCRIPTIONS
    ]
    async_add_entities(entities)


class HisenseFridgeModeSelect(HisenseEntity, SelectEntity):
    entity_description: SelectEntityDescription

    def __init__(self, coordinator, description: SelectEntityDescription):
        super().__init__(coordinator, description.key, description.key, description.icon)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return False

    @property
    def current_option(self) -> str | None:
        if self.entity_description.key == "work_mode_select":
            return self.status.get("work_mode")
        return self.status.get("variation_mode")

    async def async_select_option(self, option: str) -> None:
        raise HomeAssistantError(
            "Hisense refrigerator mode control is not available yet"
        )
