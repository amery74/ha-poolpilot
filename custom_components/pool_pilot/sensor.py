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
   PoolPilotSensorDescription(key="auto_filter_remaining_hours", translation_key="auto_filter_remaining_hours", icon="mdi:timer-sand", native_unit_of_measurement="h", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.auto_filter_remaining_hours),
   PoolPilotSensorDescription(key="auto_schedule_done_hours", translation_key="auto_schedule_done_hours", icon="mdi:timer-check-outline", native_unit_of_measurement="h", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.auto_schedule_done_hours),
   PoolPilotSensorDescription(key="smart_filtration", translation_key="smart_filtration", icon="mdi:robot-industrial-outline", value_fn=lambda d: d.auto_schedule_status, attrs_fn=lambda d: {"enabled": d.auto_schedule_enabled, "target_hours": d.auto_schedule_target_hours, "done_hours": d.auto_schedule_done_hours, "end_limit": d.auto_schedule_end_limit, "next_start": d.auto_schedule_next_start.isoformat() if d.auto_schedule_next_start else None, "windows": d.auto_schedule_windows, "detail": d.auto_schedule_detail}),
    PoolPilotSensorDescription(key="weather_factor", translation_key="weather_factor", state_class=SensorStateClass.MEASUREMENT, icon="mdi:weather-partly-cloudy", value_fn=lambda d: d.weather_factor),
    PoolPilotSensorDescription(key="chemistry_status", translation_key="chemistry_status", icon="mdi:flask", value_fn=lambda d: d.chemistry_status, attrs_fn=lambda d: {"alerts": d.alerts}),
    PoolPilotSensorDescription(key="bathing_status", translation_key="bathing_status", icon="mdi:pool", value_fn=lambda d: d.bathing_status),
    
    PoolPilotSensorDescription(key="pool_alerts", translation_key="pool_alerts", icon="mdi:alert-decagram-outline", value_fn=lambda d: len(d.pool_alerts), attrs_fn=lambda d: {"alerts": d.pool_alerts}),
    PoolPilotSensorDescription(key="algae_risk", translation_key="algae_risk", icon="mdi:leaf", native_unit_of_measurement="%", value_fn=lambda d: d.algae_risk_score, attrs_fn=lambda d: {"level": d.algae_risk_level}),
    PoolPilotSensorDescription(key="health_score", translation_key="health_score", icon="mdi:heart-pulse", native_unit_of_measurement="%", value_fn=lambda d: d.health_score, attrs_fn=lambda d: {"alerts": d.pool_alerts}),
    PoolPilotSensorDescription(key="alert_status", translation_key="alert_status", icon="mdi:alert-circle-outline", value_fn=lambda d: "Alerte" if d.has_active_alert else "Aucune alerte", attrs_fn=lambda d: {"summary": d.alert_summary, "primary_alert": d.pool_alerts[0] if d.pool_alerts else None, "pool_alerts": d.pool_alerts, "recommendations": [r.as_dict() for r in d.recommendations], "info": d.alerts, "correction_active_until": d.correction_active_until.isoformat() if d.correction_active_until else None, "correction_summary": d.correction_summary}),
    PoolPilotSensorDescription(key="action_summary", translation_key="action_summary", icon="mdi:clipboard-list-outline", value_fn=lambda d: d.action_summary, attrs_fn=lambda d: {"last_product_confirmed": d.last_product_confirmed, "last_updated": d.last_updated.isoformat() if d.last_updated else None, "recommended_filter_hours": d.recommended_filter_hours, "auto_filter_summary": d.auto_filter_summary, "auto_filter_remaining_hours": d.auto_filter_remaining_hours, "auto_schedule_status": d.auto_schedule_status, "auto_schedule_target_hours": d.auto_schedule_target_hours, "auto_schedule_done_hours": d.auto_schedule_done_hours, "recommendations": [r.as_dict() for r in d.recommendations]}),
    PoolPilotSensorDescription(key="ph", translation_key="ph", icon="mdi:ph", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.ph),
    PoolPilotSensorDescription(key="orp", translation_key="orp", native_unit_of_measurement="mV", icon="mdi:chart-bell-curve", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.orp),
    PoolPilotSensorDescription(key="free_chlorine", translation_key="free_chlorine", native_unit_of_measurement="ppm", icon="mdi:water-plus", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d.free_chlorine),
    PoolPilotSensorDescription(key="product_recommendation", translation_key="product_recommendation", icon="mdi:flask-plus", value_fn=lambda d: (f"Ajouter {round(d.recommendations[0].quantity, 2)} {d.recommendations[0].unit} de {d.recommendations[0].product_name}" if d.recommendations else "Aucune recommandation produit"), attrs_fn=lambda d: {"recommendations": [r.as_dict() for r in d.recommendations]}),
    PoolPilotSensorDescription(key="pool_house", translation_key="pool_house", icon="mdi:home-silo", value_fn=lambda d: len(d.products), attrs_fn=lambda d: {"products": [p.as_dict() for p in d.products]}),
    PoolPilotSensorDescription(key="strip_test", translation_key="strip_test", icon="mdi:test-tube", value_fn=lambda d: d.strip_test.get("updated_at_local", d.strip_test.get("updated_at", "Jamais")), attrs_fn=lambda d: dict(d.strip_test)),
    PoolPilotSensorDescription(key="strip_ph", translation_key="strip_ph", icon="mdi:ph", value_fn=lambda d: d.strip_test.get("ph"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="strip_alkalinity", translation_key="strip_alkalinity", icon="mdi:test-tube", value_fn=lambda d: d.strip_test.get("alkalinity"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "alkalinity_f": d.strip_test.get("alkalinity_f"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="strip_calcium", translation_key="strip_calcium", icon="mdi:test-tube", value_fn=lambda d: d.strip_test.get("calcium"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "calcium_f": d.strip_test.get("calcium_f"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="strip_cya", translation_key="strip_cya", icon="mdi:test-tube", value_fn=lambda d: d.strip_test.get("cya"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="strip_free_chlorine", translation_key="strip_free_chlorine", icon="mdi:test-tube", value_fn=lambda d: d.strip_test.get("free_chlorine"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="strip_total_chlorine", translation_key="strip_total_chlorine", icon="mdi:test-tube", value_fn=lambda d: d.strip_test.get("total_chlorine"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="strip_temperature", translation_key="strip_temperature", icon="mdi:thermometer", value_fn=lambda d: d.strip_test.get("temperature"), attrs_fn=lambda d: {"updated_at": d.strip_test.get("updated_at"), "source": "strip_test"}),
    PoolPilotSensorDescription(key="raw_measurements", translation_key="raw_measurements", icon="mdi:table", value_fn=lambda d: len(d.raw_measurements), attrs_fn=lambda d: {"measurements": d.raw_measurements}),
    PoolPilotSensorDescription(key="maintenance_journal", translation_key="maintenance_journal", icon="mdi:timeline-clock-outline", value_fn=lambda d: len(d.maintenance_journal), attrs_fn=lambda d: {"entries": d.maintenance_journal[:100]}),
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
