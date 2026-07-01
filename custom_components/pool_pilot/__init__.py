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
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.BUTTON, Platform.SELECT, Platform.SWITCH]

type PoolPilotConfigEntry = ConfigEntry[PoolPilotCoordinator]

ADD_PRODUCT_SCHEMA = vol.Schema({
    vol.Optional("id"): cv.string,
    vol.Required("name"): cv.string,
    vol.Optional("category", default="other"): vol.In(["ph_minus", "ph_plus", "chlorine", "bromine", "alkalinity", "stabilizer", "algaecide", "anti_algae", "wintering", "salt", "other"]),
    vol.Required("dosage_quantity"): vol.Coerce(float),
    vol.Required("dosage_unit"): cv.string,
    vol.Optional("volume_basis_m3", default=10.0): vol.Coerce(float),
    vol.Optional("effect_delta"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("stock_quantity"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("stock_unit"): cv.string,
    vol.Optional("notes"): cv.string,
}, extra=vol.ALLOW_EXTRA)
UPDATE_PRODUCT_SCHEMA = ADD_PRODUCT_SCHEMA.extend({vol.Required("id"): cv.string}, extra=vol.ALLOW_EXTRA)
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
START_AUTO_FILTER_SCHEMA = vol.Schema({vol.Optional("duration_hours"): vol.Coerce(float)})
ADD_JOURNAL_ENTRY_SCHEMA = vol.Schema({
    vol.Optional("category", default="note"): vol.In(["weather", "stock", "note", "strip_test", "equipment", "water_quality", "cleaning", "chemical", "drain", "filtration", "maintenance", "filter", "alert"]),
    vol.Optional("title"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("comment"): cv.string,
    vol.Optional("quantity"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("unit"): cv.string,
    vol.Optional("percent"): vol.Any(None, vol.Coerce(float)),
}, extra=vol.ALLOW_EXTRA)
UPDATE_JOURNAL_ENTRY_SCHEMA = vol.Schema({
    vol.Required("entry_id"): cv.string,
    vol.Optional("category"): vol.In(["weather", "stock", "note", "strip_test", "equipment", "water_quality", "cleaning", "chemical", "drain", "filtration", "maintenance", "filter", "alert"]),
    vol.Optional("title"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("comment"): cv.string,
    vol.Optional("quantity"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("unit"): cv.string,
    vol.Optional("percent"): vol.Any(None, vol.Coerce(float)),
}, extra=vol.ALLOW_EXTRA)
REMOVE_JOURNAL_ENTRY_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string})

UPDATE_STRIP_TEST_SCHEMA = vol.Schema({
    vol.Optional("ph"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("alkalinity"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("calcium"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("cya"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("free_chlorine"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("total_chlorine"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("temperature"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("air_temperature"): vol.Any(None, vol.Coerce(float)),
})

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def _coordinator() -> PoolPilotCoordinator:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ValueError("Aucune instance Pool Pilot configurée")
        return entries[0].runtime_data

    async def add_product(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_add_product(**dict(call.data))

    async def update_product(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_update_product(**dict(call.data))

    async def set_product_stock(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_set_product_stock(str(call.data["product_id"]), float(call.data["stock_quantity"]), call.data.get("stock_unit"))

    async def confirm_product_added(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_confirm_product_added(str(call.data["product_id"]), call.data.get("quantity"))

    async def remove_product(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_remove_product(str(call.data["product_id"]))

    async def start_auto_filtration(call: ServiceCall) -> None:
        c = await _coordinator()
        if call.data.get("duration_hours") is not None:
            await c.async_start_auto_filter(call.data.get("duration_hours"))
        else:
            await c.async_start_recommended_filtration()

    async def stop_auto_filtration(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_stop_recommended_filtration(turn_off=True)

    async def enable_auto_schedule(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_set_auto_schedule_enabled(True)

    async def disable_auto_schedule(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_set_auto_schedule_enabled(False)

    async def toggle_auto_schedule(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_toggle_auto_schedule()

    async def add_journal_entry(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_add_journal_entry(**dict(call.data))

    async def update_journal_entry(call: ServiceCall) -> None:
        c = await _coordinator()
        data = dict(call.data)
        entry_id = str(data.pop("entry_id"))
        await c.async_update_journal_entry(entry_id, **data)

    async def remove_journal_entry(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_remove_journal_entry(str(call.data["entry_id"]))

    async def update_strip_test(call: ServiceCall) -> None:
        c = await _coordinator()
        await c.async_update_strip_test(**dict(call.data))

    hass.services.async_register(DOMAIN, "add_product", add_product, schema=ADD_PRODUCT_SCHEMA)
    hass.services.async_register(DOMAIN, "update_product", update_product, schema=UPDATE_PRODUCT_SCHEMA)
    hass.services.async_register(DOMAIN, "set_product_stock", set_product_stock, schema=SET_STOCK_SCHEMA)
    hass.services.async_register(DOMAIN, "confirm_product_added", confirm_product_added, schema=CONFIRM_SCHEMA)
    hass.services.async_register(DOMAIN, "remove_product", remove_product, schema=REMOVE_SCHEMA)
    hass.services.async_register(DOMAIN, "start_auto_filtration", start_auto_filtration, schema=START_AUTO_FILTER_SCHEMA)
    hass.services.async_register(DOMAIN, "stop_auto_filtration", stop_auto_filtration)
    hass.services.async_register(DOMAIN, "enable_auto_schedule", enable_auto_schedule)
    hass.services.async_register(DOMAIN, "disable_auto_schedule", disable_auto_schedule)
    hass.services.async_register(DOMAIN, "toggle_auto_schedule", toggle_auto_schedule)
    hass.services.async_register(DOMAIN, "update_strip_test", update_strip_test, schema=UPDATE_STRIP_TEST_SCHEMA)
    hass.services.async_register(DOMAIN, "add_journal_entry", add_journal_entry, schema=ADD_JOURNAL_ENTRY_SCHEMA)
    hass.services.async_register(DOMAIN, "update_journal_entry", update_journal_entry, schema=UPDATE_JOURNAL_ENTRY_SCHEMA)
    hass.services.async_register(DOMAIN, "remove_journal_entry", remove_journal_entry, schema=REMOVE_JOURNAL_ENTRY_SCHEMA)
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
