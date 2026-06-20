"""Coordinator for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import logging, math, uuid, json
from typing import Any, Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.event import async_track_state_change_event, EventStateChangedData
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from .const import *

_LOGGER = logging.getLogger(__name__)
BAD_STATES = {STATE_UNKNOWN, STATE_UNAVAILABLE, None, ""}
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_pool_house"

@dataclass
class ChemicalProduct:
    id: str
    name: str
    category: str
    dosage_quantity: float
    dosage_unit: str
    volume_basis_m3: float = 10.0
    effect_delta: float | None = None
    stock_quantity: float | None = None
    stock_unit: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChemicalProduct":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            name=str(data.get("name") or "Produit"),
            category=("algaecide" if str(data.get("category") or "other") == "anti_algae" else str(data.get("category") or "other")),
            dosage_quantity=float(data.get("dosage_quantity") or 0),
            dosage_unit=str(data.get("dosage_unit") or data.get("stock_unit") or "g"),
            volume_basis_m3=float(data.get("volume_basis_m3") or 10.0),
            effect_delta=float(data["effect_delta"]) if data.get("effect_delta") not in (None, "", 0) else None,
            stock_quantity=float(data["stock_quantity"]) if data.get("stock_quantity") not in (None, "") else None,
            stock_unit=str(data.get("stock_unit") or data.get("dosage_unit") or "g"),
            notes=data.get("notes"),
        )

    def as_dict(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if self.notes:
            try:
                parsed = json.loads(self.notes)
                if isinstance(parsed, dict):
                    extra = parsed
            except Exception:
                extra = {"notes_text": self.notes}
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "dosage_quantity": self.dosage_quantity,
            "dosage_unit": self.dosage_unit,
            "volume_basis_m3": self.volume_basis_m3,
            "effect_delta": self.effect_delta,
            "stock_quantity": self.stock_quantity,
            "stock_unit": self.stock_unit,
            "notes": self.notes,
            **extra,
        }

@dataclass
class ProductRecommendation:
    product_id: str
    product_name: str
    category: str
    quantity: float
    unit: str
    reason: str
    aftercare: str = "Laisser filtrer puis contrôler à nouveau dans 24 h."
    stock_after: float | None = None
    stock_unit: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "category": self.category,
            "quantity": round(self.quantity, 2),
            "unit": self.unit,
            "reason": self.reason,
            "aftercare": self.aftercare,
            "stock_after": round(self.stock_after, 2) if self.stock_after is not None else None,
            "stock_unit": self.stock_unit,
        }

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
    recommendations: list[ProductRecommendation] = field(default_factory=list)
    products: list[ChemicalProduct] = field(default_factory=list)
    last_product_confirmed: str | None = None
    last_updated: datetime | None = None

class PoolPilotCoordinator(DataUpdateCoordinator[PoolPilotData]):
    config_entry: ConfigEntry
    _unsubscribe: Callable[[], None] | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.entry_id}", update_interval=None)
        self.config_entry = entry
        self._last_product_confirmed: str | None = None
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self.products: dict[str, ChemicalProduct] = {}

    @property
    def pool_name(self) -> str:
        return str(self.config_entry.data.get(CONF_POOL_NAME, "Piscine"))

    def option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    async def async_setup(self) -> None:
        await self.async_load_products()
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

    async def async_load_products(self) -> None:
        stored = await self._store.async_load() or {}
        self.products = {p.id: p for p in [ChemicalProduct.from_dict(x) for x in stored.get("products", [])]}

    async def async_save_products(self) -> None:
        await self._store.async_save({"products": [p.as_dict() for p in self.products.values()]})
        self.async_set_updated_data(self._calculate())

    async def async_add_product(self, **data: Any) -> str:
        product = ChemicalProduct.from_dict(data)
        self.products[product.id] = product
        await self.async_save_products()
        return product.id

    async def async_remove_product(self, product_id: str) -> None:
        self.products.pop(product_id, None)
        await self.async_save_products()

    async def async_set_product_stock(self, product_id: str, stock_quantity: float, stock_unit: str | None = None) -> None:
        if product_id not in self.products:
            raise ValueError(f"Produit inconnu: {product_id}")
        p = self.products[product_id]
        p.stock_quantity = float(stock_quantity)
        if stock_unit:
            p.stock_unit = stock_unit
        await self.async_save_products()

    async def async_confirm_product_added(self, product_id: str, quantity: float | None = None) -> None:
        if product_id not in self.products:
            raise ValueError(f"Produit inconnu: {product_id}")
        p = self.products[product_id]
        if quantity is None:
            rec = self._first_recommendation_for_category(p.category)
            quantity = rec.quantity if rec else p.dosage_quantity
        if p.stock_quantity is not None and p.stock_unit == p.dosage_unit:
            p.stock_quantity = max(0.0, p.stock_quantity - float(quantity))
        self._last_product_confirmed = f"{p.name}: {self._fmt_quantity(float(quantity), p.dosage_unit)} à {dt_util.now().strftime('%Y-%m-%d %H:%M')}"
        await self.async_save_products()

    def confirm_product(self, category: str) -> None:
        rec = self._first_recommendation_for_category(category)
        if rec:
            self.hass.async_create_task(self.async_confirm_product_added(rec.product_id, rec.quantity))
        else:
            self._last_product_confirmed = f"{category} à {dt_util.now().strftime('%Y-%m-%d %H:%M')}"
            self.async_set_updated_data(self._calculate())

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        self.async_set_updated_data(self._calculate())

    async def _async_update_data(self) -> PoolPilotData:
        return self._calculate()

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

    def _fmt_quantity(self, qty: float, unit: str) -> str:
        if unit == "g" and qty >= 1000:
            return f"{round(qty/1000, 2)} kg"
        if unit == "ml" and qty >= 1000:
            return f"{round(qty/1000, 2)} L"
        if float(qty).is_integer():
            return f"{int(qty)} {unit}"
        return f"{round(qty, 2)} {unit}"

    def _best_product(self, category: str) -> ChemicalProduct | None:
        for p in self.products.values():
            if p.category == category:
                return p
        return None

    def _first_recommendation_for_category(self, category: str) -> ProductRecommendation | None:
        data = self.data or self._calculate()
        for rec in data.recommendations:
            if rec.category == category:
                return rec
        return None

    def _dose_for_product(self, product: ChemicalProduct, delta_steps: float = 1.0) -> float:
        volume = float(self.config_entry.data.get(CONF_VOLUME_M3) or 0)
        if volume <= 0 or product.volume_basis_m3 <= 0:
            return 0.0
        return product.dosage_quantity * (volume / product.volume_basis_m3) * delta_steps

    def _build_recommendations(self, ph: float | None, fc: float | None, orp: float | None) -> list[ProductRecommendation]:
        recs: list[ProductRecommendation] = []
        target_ph = float(self.option(CONF_TARGET_PH, DEFAULT_TARGET_PH))
        target_fc = float(self.option(CONF_TARGET_FC, DEFAULT_TARGET_FC))
        if ph is not None and ph > target_ph + 0.25:
            product = self._best_product("ph_minus")
            if product:
                steps = abs(ph - target_ph) / (product.effect_delta or 0.1)
                qty = self._dose_for_product(product, steps)
                recs.append(ProductRecommendation(product.id, product.name, product.category, qty, product.dosage_unit, f"pH actuel {ph:.2f}, cible {target_ph:.2f}.", stock_after=(product.stock_quantity - qty) if product.stock_quantity is not None and product.stock_unit == product.dosage_unit else None, stock_unit=product.stock_unit))
        if ph is not None and ph < target_ph - 0.25:
            product = self._best_product("ph_plus")
            if product:
                steps = abs(target_ph - ph) / (product.effect_delta or 0.1)
                qty = self._dose_for_product(product, steps)
                recs.append(ProductRecommendation(product.id, product.name, product.category, qty, product.dosage_unit, f"pH actuel {ph:.2f}, cible {target_ph:.2f}.", stock_after=(product.stock_quantity - qty) if product.stock_quantity is not None and product.stock_unit == product.dosage_unit else None, stock_unit=product.stock_unit))
        if fc is not None and fc < target_fc * 0.75:
            product = self._best_product("chlorine")
            if product:
                delta = max(target_fc - fc, 0.1)
                steps = delta / (product.effect_delta or 1.0)
                qty = self._dose_for_product(product, steps)
                recs.append(ProductRecommendation(product.id, product.name, product.category, qty, product.dosage_unit, f"Chlore libre {fc:.2f} ppm, cible {target_fc:.2f} ppm.", stock_after=(product.stock_quantity - qty) if product.stock_quantity is not None and product.stock_unit == product.dosage_unit else None, stock_unit=product.stock_unit))
        elif fc is None and orp is not None and orp < 650:
            product = self._best_product("chlorine")
            if product:
                qty = self._dose_for_product(product, 1.0)
                recs.append(ProductRecommendation(product.id, product.name, product.category, qty, product.dosage_unit, f"RedOx bas ({orp:.0f} mV), désinfection à renforcer.", stock_after=(product.stock_quantity - qty) if product.stock_quantity is not None and product.stock_unit == product.dosage_unit else None, stock_unit=product.stock_unit))
        return recs

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
        recs = self._build_recommendations(ph, fc, orp)
        for rec in recs:
            alerts.append(f"Ajouter {self._fmt_quantity(rec.quantity, rec.unit)} de {rec.product_name}")
        bathing = "unknown"
        if chemistry_status == "ok" and temp is not None:
            bathing = "ideal" if 24 <= temp <= 30 else "ok"
        elif chemistry_status == "warning":
            bathing = "avoid"
        actions = []
        if hours is not None: actions.append(f"Filtration recommandée: {hours} h/j")
        actions.extend(alerts[:2])
        if hp_on and pump_on is False: actions.append("PAC active sans pompe détectée: sécurité à vérifier")
        return PoolPilotData(temp, ph, orp, fc, ta, ch, cya, salt, forecast, pump_on, hp_on, cover, hours, weather_factor, chemistry_status, bathing, " · ".join(actions) if actions else "Aucune action", alerts, recs, list(self.products.values()), self._last_product_confirmed, dt_util.now())
