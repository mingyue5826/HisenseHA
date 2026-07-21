from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HisenseEntity

WORK_MODE_OPTIONS = ["智能模式", "速冷"]
VARIATION_MODE_OPTIONS = ["母婴", "0℃养鲜", "原鲜"]

WORK_MODE_MAP = {
    "智能模式": 64,
    "速冷": 65,
}

VARIATION_MODE_MAP = {
    "母婴": 64,
    "0℃养鲜": 32,
    "原鲜": 16,
}

FRIDGE_SELECT_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="work_mode_select",
        translation_key="work_mode_select",
        options=WORK_MODE_OPTIONS,
        icon="mdi:format-list-bulleted",
    ),
    SelectEntityDescription(
        key="variation_mode_select",
        translation_key="variation_mode_select",
        options=VARIATION_MODE_OPTIONS,
        icon="mdi:format-list-bulleted",
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
        return True

    @property
    def current_option(self) -> str | None:
        if self.entity_description.key == "work_mode_select":
            return self.status.get("work_mode")
        return self.status.get("variation_mode")

    async def async_select_option(self, option: str) -> None:
        if self.entity_description.key == "work_mode_select":
            mode_id = WORK_MODE_MAP.get(option)
            if mode_id is None:
                raise HomeAssistantError(f"无效的工作模式选项: {option}")
            await self.coordinator.client.set_fridge_mode(mode_id)
        else:
            mode_id = VARIATION_MODE_MAP.get(option)
            if mode_id is None:
                raise HomeAssistantError(f"无效的变温模式选项: {option}")
            await self.coordinator.client.set_variation_mode(mode_id)
