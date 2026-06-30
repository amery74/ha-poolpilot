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
    @property
    def current_option(self) -> str:
        return str(self._entry.options.get(CONF_FILTERING_MODE, "auto"))
    async def async_select_option(self, option: str) -> None:
        if option not in FILTERING_MODES: return
        options = dict(self._entry.options); options[CONF_FILTERING_MODE] = option
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        if option == "auto_intelligent":
            await self.coordinator.async_set_auto_schedule_enabled(True)
        else:
            await self.coordinator.async_set_auto_schedule_enabled(False)
        await self.coordinator.async_request_refresh()
