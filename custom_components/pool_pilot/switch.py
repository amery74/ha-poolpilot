"""Switches for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .coordinator import PoolPilotCoordinator
from .entity import PoolPilotEntity

@dataclass(frozen=True, kw_only=True)
class PoolPilotSwitchDescription(SwitchEntityDescription):
    pass

SWITCHES = (
    PoolPilotSwitchDescription(
        key="auto_filter",
        translation_key="auto_filter",
        icon="mdi:lightning-bolt-auto",
    ),
    PoolPilotSwitchDescription(
        key="auto_schedule",
        translation_key="auto_schedule",
        icon="mdi:lightning-bolt-circle",
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PoolPilotCoordinator = entry.runtime_data
    async_add_entities([PoolPilotAutoFilterSwitch(coordinator, SWITCHES[0]), PoolPilotAutoScheduleSwitch(coordinator, SWITCHES[1])])

class PoolPilotAutoFilterSwitch(PoolPilotEntity, SwitchEntity):
    entity_description: PoolPilotSwitchDescription

    def __init__(self, coordinator: PoolPilotCoordinator, description: PoolPilotSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return bool(data.auto_filter_active) if data else False

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "remaining_hours": data.auto_filter_remaining_hours,
            "end": data.auto_filter_end.isoformat() if data.auto_filter_end else None,
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_start_auto_filter()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_stop_auto_filter(turn_off=True)


class PoolPilotAutoScheduleSwitch(PoolPilotEntity, SwitchEntity):
    entity_description: PoolPilotSwitchDescription

    def __init__(self, coordinator: PoolPilotCoordinator, description: PoolPilotSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return bool(data.auto_schedule_enabled) if data else False

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "status": data.auto_schedule_status,
            "windows": data.auto_schedule_windows,
            "next_start": data.auto_schedule_next_start.isoformat() if data.auto_schedule_next_start else None,
            "target_hours": data.auto_schedule_target_hours,
            "done_hours": data.auto_schedule_done_hours,
            "end_limit": data.auto_schedule_end_limit,
            "detail": data.auto_schedule_detail,
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_auto_schedule_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_auto_schedule_enabled(False)
