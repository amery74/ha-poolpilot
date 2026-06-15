"""Coordinator for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import logging, math
from typing import Any, Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.event import async_track_state_change_event, EventStateChangedData
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from .const import *

_LOGGER = logging.getLogger(__name__)
BAD_STATES = {STATE_UNKNOWN, STATE_UNAVAILABLE, None, ""}

@dataclass
class PoolPilotData:
    water_temp_c: float | None = None
    ph: float | None = None
    orp: float | None = None
    free_chlorine: float | None = None
    alkalinity: float | None = None
    calcium: float | None = None
    cya: float | None = None
    salt: float | None = None
    forecast_temp_c: float | None = None
    pump_on: bool | None = None
    heatpump_on: bool | None = None
    cover_closed: bool | None = None
    recommended_filter_hours: float | None = None
    weather_factor: float = 1.0
    chemistry_status: str = "unknown"
    bathing_status: str = "unknown"
    action_summary: str = "Aucune donnée"
    alerts: list[str] = field(default_factory=list)
    last_product_confirmed: str | None = None
    last_updated: datetime | None = None

class PoolPilotCoordinator(DataUpdateCoordinator[PoolPilotData]):
    config_entry: ConfigEntry
    _unsubscribe: Callable[[], None] | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.entry_id}", update_interval=None)
        self.config_entry = entry
        self._last_product_confirmed: str | None = None

    @property
    def pool_name(self) -> str:
        return str(self.config_entry.data.get(CONF_POOL_NAME, "Piscine"))

    def option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    async def async_setup(self) -> None:
        entities = [self.config_entry.data.get(k) for k in (
            CONF_TEMP_ENTITY, CONF_PH_ENTITY, CONF_ORP_ENTITY, CONF_FC_ENTITY, CONF_TA_ENTITY,
            CONF_CH_ENTITY, CONF_CYA_ENTITY, CONF_SALT_ENTITY, CONF_PUMP_SWITCH, CONF_HEATPUMP_ENTITY,
            CONF_WEATHER_ENTITY, CONF_FORECAST_TEMP_ENTITY, CONF_COVER_ENTITY)]
        entities = [e for e in entities if e]
        if entities:
            self._unsubscribe = async_track_state_change_event(self.hass, entities, self._async_state_changed)
        await self.async_request_refresh()

    def async_shutdown(self) -> None:
        if self._unsubscribe:
            self._unsubscribe(); self._unsubscribe = None

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        self.async_set_updated_data(self._calculate())

    async def _async_update_data(self) -> PoolPilotData:
        return self._calculate()

    def confirm_product(self, product: str) -> None:
        self._last_product_confirmed = f"{product} à {dt_util.now().strftime('%Y-%m-%d %H:%M')}"
        self.async_set_updated_data(self._calculate())

    def _state(self, entity_id: str | None) -> Any:
        if not entity_id: return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    def _float(self, entity_id: str | None) -> float | None:
        val = self._state(entity_id)
        if val in BAD_STATES: return None
        try: return float(str(val).replace(",", "."))
        except (TypeError, ValueError): return None

    def _temp_c(self, entity_id: str | None) -> float | None:
        val = self._float(entity_id)
        if val is None: return None
        st = self.hass.states.get(entity_id) if entity_id else None
        unit = st.attributes.get("unit_of_measurement") if st else None
        if unit == UnitOfTemperature.FAHRENHEIT or unit == "°F":
            return (val - 32) * 5 / 9
        return val

    def _is_on(self, entity_id: str | None) -> bool | None:
        val = self._state(entity_id)
        if val in BAD_STATES: return None
        return str(val).lower() in {"on", "heat", "heating", "cool", "auto", "open"}

    def _cover_closed(self, entity_id: str | None) -> bool | None:
        val = self._state(entity_id)
        if val in BAD_STATES: return None
        return str(val).lower() in {"on", "closed", "ferme", "fermée", "true"}

    def _filter_hours(self, water_temp: float | None, forecast: float | None, covered: bool | None) -> tuple[float | None, float]:
        if water_temp is None: return None, 1.0
        coef = float(self.option(CONF_FILTER_COEF, DEFAULT_FILTER_COEF))
        min_h = float(self.option(CONF_MIN_FILTER_HOURS, DEFAULT_MIN_FILTER_HOURS))
        max_h = float(self.option(CONF_MAX_FILTER_HOURS, DEFAULT_MAX_FILTER_HOURS))
        # Règle française classique: temps de filtration ≈ température eau / 2, configurable.
        base = water_temp / coef
        factor = 1.0
        temp_ref = max(water_temp, forecast or water_temp)
        if temp_ref >= 32: factor += 0.35
        elif temp_ref >= 28: factor += 0.20
        elif temp_ref >= 24: factor += 0.10
        if covered is True: factor -= 0.10
        hours = max(min_h, min(max_h, base * factor))
        return round(hours, 1), round(factor, 2)

    def _chemistry_status(self, ph: float | None, orp: float | None, fc: float | None) -> tuple[str, list[str]]:
        alerts: list[str] = []
        if ph is None and orp is None and fc is None: return "unknown", alerts
        status = "ok"
        target_ph = float(self.option(CONF_TARGET_PH, DEFAULT_TARGET_PH))
        if ph is not None:
            if ph > target_ph + 0.25:
                alerts.append("pH haut: correction pH- recommandée"); status = "warning"
            elif ph < target_ph - 0.25:
                alerts.append("pH bas: correction pH+ recommandée"); status = "warning"
        if fc is not None:
            target_fc = float(self.option(CONF_TARGET_FC, DEFAULT_TARGET_FC))
            if fc < target_fc * 0.75:
                alerts.append("Chlore libre bas: ajout de désinfectant recommandé"); status = "warning"
        elif orp is not None:
            if orp < 650:
                alerts.append("RedOx bas: désinfection à vérifier"); status = "warning"
            elif orp > 850:
                alerts.append("RedOx élevé: surchloration possible"); status = "warning"
        return status, alerts

    def _calculate(self) -> PoolPilotData:
        d = self.config_entry.data
        temp = self._temp_c(d.get(CONF_TEMP_ENTITY))
        forecast = self._temp_c(d.get(CONF_FORECAST_TEMP_ENTITY))
        ph = self._float(d.get(CONF_PH_ENTITY))
        orp = self._float(d.get(CONF_ORP_ENTITY))
        fc = self._float(d.get(CONF_FC_ENTITY))
        ta = self._float(d.get(CONF_TA_ENTITY))
        ch = self._float(d.get(CONF_CH_ENTITY))
        cya = self._float(d.get(CONF_CYA_ENTITY))
        salt = self._float(d.get(CONF_SALT_ENTITY))
        pump_on = self._is_on(d.get(CONF_PUMP_SWITCH))
        hp_on = self._is_on(d.get(CONF_HEATPUMP_ENTITY))
        cover = self._cover_closed(d.get(CONF_COVER_ENTITY))
        hours, weather_factor = self._filter_hours(temp, forecast, cover)
        chemistry_status, alerts = self._chemistry_status(ph, orp, fc)
        bathing = "unknown"
        if chemistry_status == "ok" and temp is not None:
            bathing = "ideal" if 24 <= temp <= 30 else "ok"
        elif chemistry_status == "warning":
            bathing = "avoid"
        actions = []
        if hours is not None: actions.append(f"Filtration recommandée: {hours} h/j")
        actions.extend(alerts[:2])
        if hp_on and pump_on is False: actions.append("PAC active sans pompe détectée: sécurité à vérifier")
        return PoolPilotData(temp, ph, orp, fc, ta, ch, cya, salt, forecast, pump_on, hp_on, cover, hours, weather_factor, chemistry_status, bathing, " · ".join(actions) if actions else "Aucune action", alerts, self._last_product_confirmed, dt_util.now())
