"""Buttons for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError
from .const import CONF_PUMP_SWITCH
from .coordinator import PoolPilotCoordinator
from .entity import PoolPilotEntity

@dataclass(frozen=True, kw_only=True)
class PoolPilotButtonDescription(ButtonEntityDescription):
    action: str

BUTTONS = (
    PoolPilotButtonDescription(key="confirm_chlorine", translation_key="confirm_chlorine", action="chlorine", icon="mdi:water-plus"),
    PoolPilotButtonDescription(key="confirm_ph_minus", translation_key="confirm_ph_minus", action="ph_minus", icon="mdi:minus-circle"),
    PoolPilotButtonDescription(key="confirm_ph_plus", translation_key="confirm_ph_plus", action="ph_plus", icon="mdi:plus-circle"),
    PoolPilotButtonDescription(key="confirm_backwash", translation_key="confirm_backwash", action="backwash", icon="mdi:filter-sync"),
    PoolPilotButtonDescription(key="confirm_current_action", translation_key="confirm_current_action", action="current_action", icon="mdi:check-circle-outline"),
    PoolPilotButtonDescription(key="start_auto_filter", translation_key="start_auto_filter", action="start_auto_filter", icon="mdi:lightning-bolt-circle"),
    PoolPilotButtonDescription(key="start_pump", translation_key="start_pump", action="start_pump", icon="mdi:play"),
    PoolPilotButtonDescription(key="stop_pump", translation_key="stop_pump", action="stop_pump", icon="mdi:stop"),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PoolPilotCoordinator = entry.runtime_data
    async_add_entities([PoolPilotButton(coordinator, desc) for desc in BUTTONS])

class PoolPilotButton(PoolPilotEntity, ButtonEntity):
    entity_description: PoolPilotButtonDescription
    def __init__(self, coordinator: PoolPilotCoordinator, description: PoolPilotButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
    async def async_press(self) -> None:
        action = self.entity_description.action
        pump = self.coordinator.config_entry.data.get(CONF_PUMP_SWITCH)
        if action in ("start_pump", "start_auto_filter"):
            if not pump: raise HomeAssistantError("Aucune entité pompe configurée")
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": pump}, blocking=True)
            await self.coordinator.async_request_refresh(); return
        if action == "stop_pump":
            if not pump: raise HomeAssistantError("Aucune entité pompe configurée")
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": pump}, blocking=True)
            await self.coordinator.async_request_refresh(); return
        if action == "current_action":
            data = self.coordinator.data
            if data and data.recommendations:
                await self.coordinator.async_confirm_product_added(data.recommendations[0].product_id, data.recommendations[0].quantity)
            else:
                self.coordinator.confirm_product("current_action")
            await self.coordinator.async_request_refresh()
            return
        self.coordinator.confirm_product(action)
