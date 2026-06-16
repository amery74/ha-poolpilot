"""Sensors for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .coordinator import PoolPilotCoordinator, PoolPilotData
from .entity import PoolPilotEntity

@dataclass(frozen=True, kw_only=True)
class PoolPilotSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PoolPilotData], Any]
    attrs_fn: Callable[[PoolPilotData], dict[str, Any]] | None = None

SENSORS = (
    PoolPilotSensorDescription(key="water_temperature", translation_key="water_temperature", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: round(d.water_temp_c,1) if d.water_temp_c is not None else None),
    PoolPilotSensorDescription(key="recommended_filter_hours", translation_key="recommended_filter_hours", native_unit_of_measurement="h", state_class=SensorStateClass.MEASUREMENT, icon="mdi:pump", value_fn=lambda d: d.recommended_filter_hours, attrs_fn=lambda d: {"weather_factor": d.weather_factor}),
    PoolPilotSensorDescription(key="weather_factor", translation_key="weather_factor", state_class=SensorStateClass.MEASUREMENT, icon="mdi:weather-partly-cloudy", value_fn=lambda d: d.weather_factor),
    PoolPilotSensorDescription(key="chemistry_status", translation_key="chemistry_status", icon="mdi:flask", value_fn=lambda d: d.chemistry_status, attrs_fn=lambda d: {"alerts": d.alerts}),
    PoolPilotSensorDescription(key="bathing_status", translation_key="bathing_status", icon="mdi:pool", value_fn=lambda d: d.bathing_status),
    PoolPilotSensorDescription(key="action_summary", translation_key="action_summary", icon="mdi:clipboard-list-outline", value_fn=lambda d: d.action_summary, attrs_fn=lambda d: {"last_product_confirmed": d.last_product_confirmed, "last_updated": d.last_updated.isoformat() if d.last_updated else None, "recommendations": [r.as_dict() for r in d.recommendations]}),
    PoolPilotSensorDescription(key="ph", translation_key="ph", icon="mdi:ph", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.ph),
    PoolPilotSensorDescription(key="orp", translation_key="orp", native_unit_of_measurement="mV", icon="mdi:chart-bell-curve", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.orp),
    PoolPilotSensorDescription(key="free_chlorine", translation_key="free_chlorine", native_unit_of_measurement="ppm", icon="mdi:water-plus", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.free_chlorine),
    PoolPilotSensorDescription(key="product_recommendation", translation_key="product_recommendation", icon="mdi:flask-plus", value_fn=lambda d: (f"Ajouter {round(d.recommendations[0].quantity, 2)} {d.recommendations[0].unit} de {d.recommendations[0].product_name}" if d.recommendations else "Aucune recommandation produit"), attrs_fn=lambda d: {"recommendations": [r.as_dict() for r in d.recommendations]}),
    PoolPilotSensorDescription(key="pool_house", translation_key="pool_house", icon="mdi:home-silo", value_fn=lambda d: len(d.products), attrs_fn=lambda d: {"products": [p.as_dict() for p in d.products]}),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PoolPilotCoordinator = entry.runtime_data
    async_add_entities([PoolPilotSensor(coordinator, desc) for desc in SENSORS])

class PoolPilotSensor(PoolPilotEntity, SensorEntity):
    entity_description: PoolPilotSensorDescription
    def __init__(self, coordinator: PoolPilotCoordinator, description: PoolPilotSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data or not self.entity_description.attrs_fn:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
