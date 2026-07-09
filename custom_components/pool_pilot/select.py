"""Select entities for Pool Pilot."""
from __future__ import annotations
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import CONF_FILTERING_MODE, FILTERING_MODES
from .coordinator import PoolPilotCoordinator
from .entity import PoolPilotEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PoolPilotCoordinator = entry.runtime_data
    async_add_entities([PoolPilotFilteringModeSelect(coordinator, entry)])

class PoolPilotFilteringModeSelect(PoolPilotEntity, SelectEntity):
    _attr_options = FILTERING_MODES
    entity_description = SelectEntityDescription(key="filtering_mode", translation_key="filtering_mode", icon="mdi:tune")

    def __init__(self, coordinator: PoolPilotCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, "filtering_mode")
        self._entry = entry

    def _normalized_mode(self, value: str | None) -> str:
        if value == "auto_intelligent":
            return "auto"
        if value in FILTERING_MODES:
            return value
        return "auto"

    @property
    def current_option(self) -> str:
        return self._normalized_mode(self._entry.options.get(CONF_FILTERING_MODE, "auto"))

    async def async_select_option(self, option: str) -> None:
        option = self._normalized_mode(option)
        if option not in FILTERING_MODES:
            option = "auto"

        options = dict(self._entry.options)
        options[CONF_FILTERING_MODE] = option
        self.hass.config_entries.async_update_entry(self._entry, options=options)

        await self.coordinator.async_set_auto_schedule_enabled(option == "auto")
        await self.coordinator.async_request_refresh()
