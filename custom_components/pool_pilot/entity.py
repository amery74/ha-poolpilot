"""Base entity for Pool Pilot."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, VERSION
from .coordinator import PoolPilotCoordinator


class PoolPilotEntity(CoordinatorEntity[PoolPilotCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PoolPilotCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._pool_pilot_key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.pool_name,
            manufacturer="Pool Pilot",
            model="Home Assistant Pool Supervisor",
            sw_version=VERSION,
        )

    @property
    def pool_pilot_discovery_attributes(self) -> dict[str, str]:
        """Stable metadata used by Pool Pilot Dashboard auto-discovery."""
        return {
            "pool_pilot_key": self._pool_pilot_key,
            "pool_pilot_instance": self.coordinator.config_entry.entry_id,
            "pool_pilot_domain": DOMAIN,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose stable discovery metadata on every Pool Pilot entity."""
        return dict(self.pool_pilot_discovery_attributes)
