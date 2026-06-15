"""Pool Pilot integration."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.const import Platform
from .const import DOMAIN
from .coordinator import PoolPilotCoordinator

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.BUTTON, Platform.SELECT]

type PoolPilotConfigEntry = ConfigEntry[PoolPilotCoordinator]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: PoolPilotConfigEntry) -> bool:
    coordinator = PoolPilotCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: PoolPilotConfigEntry) -> bool:
    coordinator = entry.runtime_data
    coordinator.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_reload_entry(hass: HomeAssistant, entry: PoolPilotConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
