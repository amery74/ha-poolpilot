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

class PoolPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PoolPilotOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            await self.async_set_unique_id(str(user_input[CONF_POOL_NAME]).lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()
            return await self.async_step_entities()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_POOL_NAME, default="Piscine"): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_VOLUME_M3, default=50.0): NumberSelector(NumberSelectorConfig(min=1, max=500, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="m³")),
            vol.Required(CONF_POOL_TYPE, default=POOL_TYPE_CHLORINE): SelectSelector(SelectSelectorConfig(options=POOL_TYPES, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_SURFACE_TYPE, default="liner"): SelectSelector(SelectSelectorConfig(options=SURFACE_TYPES, mode=SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return self.async_create_entry(title=self._data[CONF_POOL_NAME], data=self._data, options={
                CONF_TARGET_PH: DEFAULT_TARGET_PH,
                CONF_TARGET_FC: DEFAULT_TARGET_FC,
                CONF_FILTERING_MODE: "auto",
                CONF_FILTER_COEF: DEFAULT_FILTER_COEF,
                CONF_MIN_FILTER_HOURS: DEFAULT_MIN_FILTER_HOURS,
                CONF_MAX_FILTER_HOURS: DEFAULT_MAX_FILTER_HOURS,
                CONF_HEAT_PUMP_PRIORITY: True,
                CONF_FREE_CHLORINE_MODE: DEFAULT_FREE_CHLORINE_MODE,
            })
        sensor = EntitySelector(EntitySelectorConfig(domain="sensor"))
        switch = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
        hp = EntitySelector(EntitySelectorConfig(domain=["climate", "switch", "water_heater"] ))
        weather = EntitySelector(EntitySelectorConfig(domain="weather"))
        binary = EntitySelector(EntitySelectorConfig(domain=["binary_sensor", "input_boolean", "cover", "switch"]))
        return self.async_show_form(step_id="entities", data_schema=vol.Schema({
            vol.Required(CONF_TEMP_ENTITY): sensor,
            vol.Optional(CONF_PH_ENTITY): sensor,
            vol.Optional(CONF_ORP_ENTITY): sensor,
            vol.Optional(CONF_FC_ENTITY): sensor,
            vol.Optional(CONF_TA_ENTITY): sensor,
            vol.Optional(CONF_CH_ENTITY): sensor,
            vol.Optional(CONF_CYA_ENTITY): sensor,
            vol.Optional(CONF_SALT_ENTITY): sensor,
            vol.Optional(CONF_PUMP_SWITCH): switch,
            vol.Optional(CONF_HEATPUMP_ENTITY): hp,
            vol.Optional(CONF_WEATHER_ENTITY): weather,
            vol.Optional(CONF_FORECAST_TEMP_ENTITY): sensor,
            vol.Optional(CONF_COVER_ENTITY): binary,
        }))

class PoolPilotOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        cur = self.config_entry.options
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_TARGET_PH, default=cur.get(CONF_TARGET_PH, DEFAULT_TARGET_PH)): NumberSelector(NumberSelectorConfig(min=6.8, max=8.0, step=0.1, mode=NumberSelectorMode.SLIDER)),
            vol.Required(CONF_TARGET_FC, default=cur.get(CONF_TARGET_FC, DEFAULT_TARGET_FC)): NumberSelector(NumberSelectorConfig(min=0.5, max=10, step=0.1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="ppm")),
            vol.Required(CONF_FILTERING_MODE, default=cur.get(CONF_FILTERING_MODE, "auto")): SelectSelector(SelectSelectorConfig(options=FILTERING_MODES, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_FILTER_COEF, default=cur.get(CONF_FILTER_COEF, DEFAULT_FILTER_COEF)): NumberSelector(NumberSelectorConfig(min=1.0, max=4.0, step=0.1, mode=NumberSelectorMode.BOX)),
            vol.Required(CONF_MIN_FILTER_HOURS, default=cur.get(CONF_MIN_FILTER_HOURS, DEFAULT_MIN_FILTER_HOURS)): NumberSelector(NumberSelectorConfig(min=0, max=24, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="h")),
            vol.Required(CONF_MAX_FILTER_HOURS, default=cur.get(CONF_MAX_FILTER_HOURS, DEFAULT_MAX_FILTER_HOURS)): NumberSelector(NumberSelectorConfig(min=1, max=24, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="h")),
            vol.Required(CONF_HEAT_PUMP_PRIORITY, default=cur.get(CONF_HEAT_PUMP_PRIORITY, True)): BooleanSelector(),
            vol.Required(CONF_FREE_CHLORINE_MODE, default=cur.get(CONF_FREE_CHLORINE_MODE, DEFAULT_FREE_CHLORINE_MODE)): BooleanSelector(),
        }))
