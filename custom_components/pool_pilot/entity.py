"""Base entity for Pool Pilot."""
from __future__ import annotations
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, VERSION
from .coordinator import PoolPilotCoordinator

class PoolPilotEntity(CoordinatorEntity[PoolPilotCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PoolPilotCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.pool_name,
            manufacturer="Pool Pilot",
            model="Home Assistant Pool Supervisor",
            sw_version=VERSION,
        )
