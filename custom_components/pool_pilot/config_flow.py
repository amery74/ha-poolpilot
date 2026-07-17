"""Config flow for Pool Pilot."""
from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector, TextSelectorConfig, TextSelectorType,
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    EntitySelector, EntitySelectorConfig, BooleanSelector,
)
from .const import *

TREATMENT_TYPE_OPTIONS = [
    {"value": POOL_TYPE_CHLORINE, "label": "Chlore"},
    {"value": POOL_TYPE_SALT, "label": "Électrolyse au sel"},
    {"value": POOL_TYPE_BROMINE, "label": "Brome"},
]

SURFACE_TYPE_OPTIONS = [
    {"value": "liner", "label": "Liner"},
    {"value": "polyester", "label": "Coque polyester"},
    {"value": "concrete", "label": "Béton"},
    {"value": "tile", "label": "Carrelage"},
    {"value": "painted", "label": "Peinture"},
    {"value": "other", "label": "Autre"},
]

CHLORINE_MODE_OPTIONS = [
    {"value": "measured", "label": "Chlore mesuré — l’appareil expose une entité chlore libre"},
    {"value": "estimated", "label": "Chlore estimé — ORP + pH + température, stabilisant via bandelette"},
]


DISINFECTION_MODE_OPTIONS = [
    {"value": MEASUREMENT_MODE_ORP, "label": "ORP / RedOx (mV)"},
    {"value": MEASUREMENT_MODE_CHLORINE, "label": "Chlore libre (ppm)"},
]

ELECTROLYZER_TYPE_OPTIONS = [
    {"value": ELECTROLYZER_TYPE_NONE, "label": "Aucun électrolyseur"},
    {"value": ELECTROLYZER_TYPE_SIMPLE, "label": "Simple — marche / arrêt"},
    {"value": ELECTROLYZER_TYPE_ADVANCED, "label": "Avancé — marche / arrêt, production et Boost"},
]

FILTRATION_PLACEMENT_OPTIONS = [
    {"value": FILTRATION_PLACEMENT_CENTERED, "label": "Centrer la durée calculée autour d’une heure"},
    {"value": FILTRATION_PLACEMENT_WINDOW, "label": "Respecter une heure de début minimale et une heure de fin maximale"},
]


FILTERING_MODE_OPTIONS = [
    {"value": "off", "label": "Arrêt"},
    {"value": "manual", "label": "Manuel"},
    {"value": "auto", "label": "Automatique"},
]

class PoolPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 6

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PoolPilotOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update({k: v for k, v in user_input.items() if v not in (None, "")})
            await self.async_set_unique_id(str(user_input[CONF_POOL_NAME]).lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()
            return await self.async_step_entities()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_POOL_NAME, default="Piscine"): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_VOLUME_M3, default=50.0): NumberSelector(NumberSelectorConfig(min=1, max=500, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="m³")),
            vol.Required(CONF_POOL_TYPE, default=POOL_TYPE_CHLORINE): SelectSelector(SelectSelectorConfig(options=TREATMENT_TYPE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_SURFACE_TYPE, default="liner"): SelectSelector(SelectSelectorConfig(options=SURFACE_TYPE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_DISINFECTION_MODE, default=DEFAULT_DISINFECTION_MODE): SelectSelector(SelectSelectorConfig(options=DISINFECTION_MODE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_ELECTROLYZER_TYPE, default=DEFAULT_ELECTROLYZER_TYPE): SelectSelector(SelectSelectorConfig(options=ELECTROLYZER_TYPE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return self.async_create_entry(title=self._data[CONF_POOL_NAME], data=self._data, options={
                CONF_TARGET_PH: DEFAULT_TARGET_PH,
                CONF_TARGET_FC: DEFAULT_TARGET_FC,
                CONF_FILTERING_MODE: "auto",
                CONF_AUTO_START_TIME: DEFAULT_AUTO_START_TIME,
                CONF_AUTO_END_TIME: DEFAULT_AUTO_END_TIME,
                CONF_FILTER_COEF: DEFAULT_FILTER_COEF,
                CONF_MIN_FILTER_HOURS: DEFAULT_MIN_FILTER_HOURS,
                CONF_MAX_FILTER_HOURS: DEFAULT_MAX_FILTER_HOURS,
                CONF_FREE_CHLORINE_MODE: DEFAULT_FREE_CHLORINE_MODE,
                CONF_DISINFECTION_MODE: self._data.get(CONF_DISINFECTION_MODE, DEFAULT_DISINFECTION_MODE),
                CONF_ELECTROLYZER_TYPE: self._data.get(CONF_ELECTROLYZER_TYPE, DEFAULT_ELECTROLYZER_TYPE),
                CONF_FILTRATION_PLACEMENT_MODE: DEFAULT_FILTRATION_PLACEMENT_MODE,
                CONF_FILTRATION_CENTER_HOUR: DEFAULT_FILTRATION_CENTER_HOUR,
            })
        sensor = EntitySelector(EntitySelectorConfig(domain="sensor"))
        switch = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
        pump_state = EntitySelector(EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean"]))
        weather = EntitySelector(EntitySelectorConfig(domain="weather"))
        electrolyzer_switch = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
        electrolyzer_output = EntitySelector(EntitySelectorConfig(domain=["number", "input_number", "sensor"]))
        electrolyzer_boost = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean", "button"]))
        any_state = EntitySelector(EntitySelectorConfig())
        mode = self._data.get(CONF_DISINFECTION_MODE, DEFAULT_DISINFECTION_MODE)
        electrolyzer_type = self._data.get(CONF_ELECTROLYZER_TYPE, DEFAULT_ELECTROLYZER_TYPE)
        schema = {
            vol.Required(CONF_TEMP_ENTITY): sensor,
            vol.Optional(CONF_PUMP_SWITCH): switch,
            vol.Optional(CONF_PUMP_STATE): pump_state,
            vol.Required(CONF_WEATHER_ENTITY): weather,
            vol.Optional(CONF_PH_ENTITY): sensor,
            (vol.Required(CONF_ORP_ENTITY) if mode == MEASUREMENT_MODE_ORP else vol.Optional(CONF_ORP_ENTITY)): sensor,
            (vol.Required(CONF_FC_ENTITY) if mode == MEASUREMENT_MODE_CHLORINE else vol.Optional(CONF_FC_ENTITY)): sensor,
            vol.Optional(CONF_SALT_ENTITY): sensor,
        }
        if electrolyzer_type != ELECTROLYZER_TYPE_NONE:
            schema[vol.Optional(CONF_ELECTROLYZER_SWITCH)] = electrolyzer_switch
            schema[vol.Optional(CONF_ELECTROLYZER_STATUS_ENTITY)] = any_state
        if electrolyzer_type == ELECTROLYZER_TYPE_ADVANCED:
            schema[vol.Optional(CONF_ELECTROLYZER_OUTPUT_ENTITY)] = electrolyzer_output
            schema[vol.Optional(CONF_ELECTROLYZER_BOOST_ENTITY)] = electrolyzer_boost
        return self.async_show_form(step_id="entities", data_schema=vol.Schema(schema))

class PoolPilotOptionsFlow(OptionsFlow):
    """Robust options flow.

    Uses a private _entry attribute instead of assigning to OptionsFlow.config_entry.
    This avoids a 500 error on HA versions where config_entry is read-only.
    The form is intentionally limited to the core Pool Pilot settings; PAC, cover,
    TAC, TH and stabilizer are managed from the dashboard expert menu instead.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    def _current(self, key: str, default: Any = None) -> Any:
        value = self._entry.options.get(key, self._entry.data.get(key, default))
        if key == CONF_FILTERING_MODE and value == "auto_intelligent":
            return "auto"
        return default if value is None else value

    def _optional_entity(self, key: str) -> Any:
        current = self._current(key, None)
        if current in (None, ""):
            return vol.Optional(key)
        return vol.Optional(key, default=current)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            data_keys = {
                CONF_POOL_NAME, CONF_VOLUME_M3, CONF_POOL_TYPE, CONF_SURFACE_TYPE,
                CONF_TEMP_ENTITY, CONF_PH_ENTITY, CONF_ORP_ENTITY, CONF_FC_ENTITY,
                CONF_SALT_ENTITY, CONF_PUMP_SWITCH, CONF_PUMP_STATE, CONF_WEATHER_ENTITY,
                CONF_ELECTROLYZER_SWITCH, CONF_ELECTROLYZER_OUTPUT_ENTITY,
                CONF_ELECTROLYZER_BOOST_ENTITY, CONF_ELECTROLYZER_STATUS_ENTITY,
            }
            option_keys = {
                CONF_TARGET_PH, CONF_TARGET_FC, CONF_FILTERING_MODE,
                CONF_FILTER_COEF, CONF_MIN_FILTER_HOURS, CONF_MAX_FILTER_HOURS,
                CONF_FREE_CHLORINE_MODE, CONF_DISINFECTION_MODE, CONF_ELECTROLYZER_TYPE,
                CONF_FILTRATION_PLACEMENT_MODE, CONF_FILTRATION_CENTER_HOUR, CONF_AUTO_START_TIME, CONF_AUTO_END_TIME,
                CONF_NOTIFICATIONS_ENABLED, CONF_NOTIFY_PERSISTENT, CONF_NOTIFY_MOBILE_SERVICES,
                CONF_NOTIFY_DAILY_SUMMARY_ENABLED, CONF_NOTIFY_DAILY_SUMMARY_TIME, CONF_NOTIFY_STOCK_LOW_ENABLED,
                CONF_NOTIFY_BATTERY_LOW_ENABLED, CONF_NOTIFY_STRIP_TEST_DAYS, CONF_NOTIFY_STRIP_TEST_ENABLED, CONF_NOTIFY_FILTRATION_ENABLED, CONF_NOTIFY_RECOMMENDATIONS_ENABLED, CONF_NOTIFY_ALERTS_ENABLED,
            }
            new_data = dict(self._entry.data)
            new_options = dict(self._entry.options)
            for key, value in user_input.items():
                if key in data_keys:
                    if value in (None, ""):
                        new_data.pop(key, None)
                    else:
                        new_data[key] = value
                elif key in option_keys:
                    new_options[key] = value
            self.hass.config_entries.async_update_entry(
                self._entry,
                title=str(new_data.get(CONF_POOL_NAME, self._entry.title)),
                data=new_data,
            )
            return self.async_create_entry(title="", data=new_options)

        sensor = EntitySelector(EntitySelectorConfig(domain="sensor"))
        switch = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
        pump_state = EntitySelector(EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean"]))
        weather = EntitySelector(EntitySelectorConfig(domain="weather"))
        electrolyzer_switch = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
        electrolyzer_output = EntitySelector(EntitySelectorConfig(domain=["number", "input_number", "sensor"]))
        electrolyzer_boost = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean", "button"]))
        any_state = EntitySelector(EntitySelectorConfig())
        schema = {
            vol.Required(CONF_POOL_NAME, default=self._current(CONF_POOL_NAME, "Piscine")): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_VOLUME_M3, default=self._current(CONF_VOLUME_M3, 50.0)): NumberSelector(NumberSelectorConfig(min=1, max=500, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="m³")),
            vol.Required(CONF_POOL_TYPE, default=self._current(CONF_POOL_TYPE, POOL_TYPE_CHLORINE)): SelectSelector(SelectSelectorConfig(options=TREATMENT_TYPE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_SURFACE_TYPE, default=self._current(CONF_SURFACE_TYPE, "liner")): SelectSelector(SelectSelectorConfig(options=SURFACE_TYPE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_DISINFECTION_MODE, default=self._current(CONF_DISINFECTION_MODE, DEFAULT_DISINFECTION_MODE)): SelectSelector(SelectSelectorConfig(options=DISINFECTION_MODE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_ELECTROLYZER_TYPE, default=self._current(CONF_ELECTROLYZER_TYPE, DEFAULT_ELECTROLYZER_TYPE)): SelectSelector(SelectSelectorConfig(options=ELECTROLYZER_TYPE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            (vol.Required(CONF_TEMP_ENTITY, default=self._current(CONF_TEMP_ENTITY)) if self._current(CONF_TEMP_ENTITY, None) else vol.Required(CONF_TEMP_ENTITY)): sensor,
            self._optional_entity(CONF_PUMP_SWITCH): switch,
            self._optional_entity(CONF_PUMP_STATE): pump_state,
            (vol.Required(CONF_WEATHER_ENTITY, default=self._current(CONF_WEATHER_ENTITY)) if self._current(CONF_WEATHER_ENTITY, None) else vol.Required(CONF_WEATHER_ENTITY)): weather,
            self._optional_entity(CONF_PH_ENTITY): sensor,
            self._optional_entity(CONF_ORP_ENTITY): sensor,
            self._optional_entity(CONF_FC_ENTITY): sensor,
            self._optional_entity(CONF_SALT_ENTITY): sensor,
            self._optional_entity(CONF_ELECTROLYZER_SWITCH): electrolyzer_switch,
            self._optional_entity(CONF_ELECTROLYZER_OUTPUT_ENTITY): electrolyzer_output,
            self._optional_entity(CONF_ELECTROLYZER_BOOST_ENTITY): electrolyzer_boost,
            self._optional_entity(CONF_ELECTROLYZER_STATUS_ENTITY): any_state,
            vol.Required(CONF_TARGET_PH, default=self._current(CONF_TARGET_PH, DEFAULT_TARGET_PH)): NumberSelector(NumberSelectorConfig(min=6.8, max=8.0, step=0.1, mode=NumberSelectorMode.SLIDER)),
            vol.Required(CONF_TARGET_FC, default=self._current(CONF_TARGET_FC, DEFAULT_TARGET_FC)): NumberSelector(NumberSelectorConfig(min=0.5, max=10, step=0.1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="ppm")),
            vol.Required(CONF_FILTERING_MODE, default=self._current(CONF_FILTERING_MODE, "auto")): SelectSelector(SelectSelectorConfig(options=FILTERING_MODE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_FILTRATION_PLACEMENT_MODE, default=self._current(CONF_FILTRATION_PLACEMENT_MODE, DEFAULT_FILTRATION_PLACEMENT_MODE)): SelectSelector(SelectSelectorConfig(options=FILTRATION_PLACEMENT_OPTIONS, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_FILTRATION_CENTER_HOUR, default=self._current(CONF_FILTRATION_CENTER_HOUR, DEFAULT_FILTRATION_CENTER_HOUR)): NumberSelector(NumberSelectorConfig(min=0, max=23.5, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="h")),
            vol.Required(CONF_AUTO_START_TIME, default=self._current(CONF_AUTO_START_TIME, DEFAULT_AUTO_START_TIME)): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_AUTO_END_TIME, default=self._current(CONF_AUTO_END_TIME, DEFAULT_AUTO_END_TIME)): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_FILTER_COEF, default=self._current(CONF_FILTER_COEF, DEFAULT_FILTER_COEF)): NumberSelector(NumberSelectorConfig(min=1.0, max=4.0, step=0.1, mode=NumberSelectorMode.BOX)),
            vol.Required(CONF_MIN_FILTER_HOURS, default=self._current(CONF_MIN_FILTER_HOURS, DEFAULT_MIN_FILTER_HOURS)): NumberSelector(NumberSelectorConfig(min=0, max=24, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="h")),
            vol.Required(CONF_MAX_FILTER_HOURS, default=self._current(CONF_MAX_FILTER_HOURS, DEFAULT_MAX_FILTER_HOURS)): NumberSelector(NumberSelectorConfig(min=1, max=24, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="h")),
            vol.Required(CONF_NOTIFICATIONS_ENABLED, default=self._current(CONF_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_PERSISTENT, default=self._current(CONF_NOTIFY_PERSISTENT, DEFAULT_NOTIFY_PERSISTENT)): BooleanSelector(),
            vol.Optional(CONF_NOTIFY_MOBILE_SERVICES, default=self._current(CONF_NOTIFY_MOBILE_SERVICES, "")): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_NOTIFY_DAILY_SUMMARY_ENABLED, default=self._current(CONF_NOTIFY_DAILY_SUMMARY_ENABLED, DEFAULT_NOTIFY_DAILY_SUMMARY_ENABLED)): BooleanSelector(),
            vol.Optional(CONF_NOTIFY_DAILY_SUMMARY_TIME, default=self._current(CONF_NOTIFY_DAILY_SUMMARY_TIME, DEFAULT_NOTIFY_DAILY_SUMMARY_TIME)): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_NOTIFY_ALERTS_ENABLED, default=self._current(CONF_NOTIFY_ALERTS_ENABLED, DEFAULT_NOTIFY_ALERTS_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_RECOMMENDATIONS_ENABLED, default=self._current(CONF_NOTIFY_RECOMMENDATIONS_ENABLED, DEFAULT_NOTIFY_RECOMMENDATIONS_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_FILTRATION_ENABLED, default=self._current(CONF_NOTIFY_FILTRATION_ENABLED, DEFAULT_NOTIFY_FILTRATION_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_STOCK_LOW_ENABLED, default=self._current(CONF_NOTIFY_STOCK_LOW_ENABLED, DEFAULT_NOTIFY_STOCK_LOW_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_BATTERY_LOW_ENABLED, default=self._current(CONF_NOTIFY_BATTERY_LOW_ENABLED, DEFAULT_NOTIFY_BATTERY_LOW_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_STRIP_TEST_ENABLED, default=self._current(CONF_NOTIFY_STRIP_TEST_ENABLED, DEFAULT_NOTIFY_STRIP_TEST_ENABLED)): BooleanSelector(),
            vol.Required(CONF_NOTIFY_STRIP_TEST_DAYS, default=self._current(CONF_NOTIFY_STRIP_TEST_DAYS, DEFAULT_NOTIFY_STRIP_TEST_DAYS)): NumberSelector(NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="j")),
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
