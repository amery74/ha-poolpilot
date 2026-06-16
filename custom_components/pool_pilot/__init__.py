"""Pool Pilot integration."""
from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.const import Platform
from .const import DOMAIN
from .coordinator import PoolPilotCoordinator

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.BUTTON, Platform.SELECT]

type PoolPilotConfigEntry = ConfigEntry[PoolPilotCoordinator]

ADD_PRODUCT_SCHEMA = vol.Schema({
    vol.Optional("id"): cv.string,
    vol.Required("name"): cv.string,
    vol.Required("category"): vol.In(["ph_minus", "ph_plus", "chlorine", "bromine", "alkalinity", "stabilizer", "algaecide", "salt", "other"]),
    vol.Required("dosage_quantity"): vol.Coerce(float),
    vol.Required("dosage_unit"): cv.string,
    vol.Optional("volume_basis_m3", default=10.0): vol.Coerce(float),
    vol.Optional("effect_delta"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("stock_quantity"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("stock_unit"): cv.string,
    vol.Optional("notes"): cv.string,
})
SET_STOCK_SCHEMA = vol.Schema({
    vol.Required("product_id"): cv.string,
    vol.Required("stock_quantity"): vol.Coerce(float),
    vol.Optional("stock_unit"): cv.string,
})
CONFIRM_SCHEMA = vol.Schema({
    vol.Required("product_id"): cv.string,
    vol.Optional("quantity"): vol.Any(None, vol.Coerce(float)),
})
REMOVE_SCHEMA = vol.Schema({vol.Required("product_id"): cv.string})

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def _coordinator() -> PoolPilotCoordinator:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ValueError("Aucune instance Pool Pilot configurée")
        return entries[0].runtime_data

    async def add_product(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_add_product(**dict(call.data))

    async def set_product_stock(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_set_product_stock(str(call.data["product_id"]), float(call.data["stock_quantity"]), call.data.get("stock_unit"))

    async def confirm_product_added(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_confirm_product_added(str(call.data["product_id"]), call.data.get("quantity"))

    async def remove_product(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_remove_product(str(call.data["product_id"]))

    hass.services.async_register(DOMAIN, "add_product", add_product, schema=ADD_PRODUCT_SCHEMA)
    hass.services.async_register(DOMAIN, "set_product_stock", set_product_stock, schema=SET_STOCK_SCHEMA)
    hass.services.async_register(DOMAIN, "confirm_product_added", confirm_product_added, schema=CONFIRM_SCHEMA)
    hass.services.async_register(DOMAIN, "remove_product", remove_product, schema=REMOVE_SCHEMA)
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
