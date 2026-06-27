"""Number entities for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass
from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import *
from .coordinator import PoolPilotCoordinator
from .entity import PoolPilotEntity

@dataclass(frozen=True, kw_only=True)
class PoolPilotNumberDescription(NumberEntityDescription):
    config_key: str
    default_value: float

NUMBERS = (
    PoolPilotNumberDescription(key="target_ph", translation_key="target_ph", config_key=CONF_TARGET_PH, default_value=DEFAULT_TARGET_PH, native_min_value=6.8, native_max_value=8.0, native_step=0.1, mode=NumberMode.SLIDER, icon="mdi:ph"),
    PoolPilotNumberDescription(key="target_fc", translation_key="target_fc", config_key=CONF_TARGET_FC, default_value=DEFAULT_TARGET_FC, native_min_value=0.5, native_max_value=10, native_step=0.1, native_unit_of_measurement="ppm", mode=NumberMode.SLIDER, icon="mdi:water-plus"),
    PoolPilotNumberDescription(key="filter_coef", translation_key="filter_coef", config_key=CONF_FILTER_COEF, default_value=DEFAULT_FILTER_COEF, native_min_value=1, native_max_value=4, native_step=0.1, mode=NumberMode.BOX, icon="mdi:division"),
    PoolPilotNumberDescription(key="min_filter_hours", translation_key="min_filter_hours", config_key=CONF_MIN_FILTER_HOURS, default_value=DEFAULT_MIN_FILTER_HOURS, native_min_value=0, native_max_value=24, native_step=0.5, native_unit_of_measurement="h", mode=NumberMode.BOX, icon="mdi:timer-outline"),
    PoolPilotNumberDescription(key="max_filter_hours", translation_key="max_filter_hours", config_key=CONF_MAX_FILTER_HOURS, default_value=DEFAULT_MAX_FILTER_HOURS, native_min_value=1, native_max_value=24, native_step=0.5, native_unit_of_measurement="h", mode=NumberMode.BOX, icon="mdi:timer"),
    PoolPilotNumberDescription(key="water_temp_alert_min", translation_key="water_temp_alert_min", config_key=CONF_WATER_TEMP_ALERT_MIN, default_value=DEFAULT_WATER_TEMP_ALERT_MIN, native_min_value=-5, native_max_value=30, native_step=0.1, native_unit_of_measurement="°C", mode=NumberMode.BOX, icon="mdi:snowflake"),
    PoolPilotNumberDescription(key="water_temp_alert_max", translation_key="water_temp_alert_max", config_key=CONF_WATER_TEMP_ALERT_MAX, default_value=DEFAULT_WATER_TEMP_ALERT_MAX, native_min_value=10, native_max_value=45, native_step=0.1, native_unit_of_measurement="°C", mode=NumberMode.BOX, icon="mdi:thermometer"),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PoolPilotCoordinator = entry.runtime_data
    async_add_entities([PoolPilotNumber(coordinator, entry, desc) for desc in NUMBERS])

class PoolPilotNumber(PoolPilotEntity, NumberEntity):
    entity_description: PoolPilotNumberDescription
    def __init__(self, coordinator: PoolPilotCoordinator, entry: ConfigEntry, description: PoolPilotNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self._entry = entry
        self.entity_description = description
    @property
    def native_value(self) -> float:
        return float(self._entry.options.get(self.entity_description.config_key, self.entity_description.default_value))
    async def async_set_native_value(self, value: float) -> None:
        options = dict(self._entry.options)
        options[self.entity_description.config_key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()
