"""Time entities for Pool Pilot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_AUTO_END_TIME,
    CONF_AUTO_START_TIME,
    DEFAULT_AUTO_END_TIME,
    DEFAULT_AUTO_START_TIME,
)
from .coordinator import PoolPilotCoordinator
from .entity import PoolPilotEntity


@dataclass(frozen=True, kw_only=True)
class PoolPilotTimeDescription(TimeEntityDescription):
    """Description of a Pool Pilot time entity."""

    config_key: str
    default_value: str


TIMES = (
    PoolPilotTimeDescription(
        key="auto_start_time",
        translation_key="auto_start_time",
        config_key=CONF_AUTO_START_TIME,
        default_value=DEFAULT_AUTO_START_TIME,
        icon="mdi:clock-start",
    ),
    PoolPilotTimeDescription(
        key="auto_end_time",
        translation_key="auto_end_time",
        config_key=CONF_AUTO_END_TIME,
        default_value=DEFAULT_AUTO_END_TIME,
        icon="mdi:clock-end",
    ),
)


def _parse_time(value: object, default: str) -> time:
    """Convert a stored HH:MM or HH:MM:SS value to datetime.time."""
    raw = str(value or default).strip()
    try:
        parts = raw.split(":")
        hour = max(0, min(23, int(parts[0])))
        minute = max(0, min(59, int(parts[1])))
        second = max(0, min(59, int(parts[2]))) if len(parts) > 2 else 0
        return time(hour=hour, minute=minute, second=second)
    except (TypeError, ValueError, IndexError):
        hour, minute = (int(part) for part in default.split(":", 1))
        return time(hour=hour, minute=minute)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Pilot time entities."""
    coordinator: PoolPilotCoordinator = entry.runtime_data
    async_add_entities(
        [PoolPilotTime(coordinator, entry, description) for description in TIMES]
    )


class PoolPilotTime(PoolPilotEntity, TimeEntity):
    """Editable time stored in the Pool Pilot config-entry options."""

    entity_description: PoolPilotTimeDescription

    def __init__(
        self,
        coordinator: PoolPilotCoordinator,
        entry: ConfigEntry,
        description: PoolPilotTimeDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self._entry = entry
        self.entity_description = description

    @property
    def native_value(self) -> time:
        value = self._entry.options.get(
            self.entity_description.config_key,
            self._entry.data.get(
                self.entity_description.config_key,
                self.entity_description.default_value,
            ),
        )
        return _parse_time(value, self.entity_description.default_value)

    async def async_set_value(self, value: time) -> None:
        options = dict(self._entry.options)
        options[self.entity_description.config_key] = value.strftime("%H:%M")
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()
