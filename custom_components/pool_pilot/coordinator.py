"""Coordinator for Pool Pilot."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging, math, uuid, json
from typing import Any, Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.event import async_track_state_change_event, EventStateChangedData, async_call_later, async_track_time_interval
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
        raw_notes = data.get("notes")
        notes_payload: dict[str, Any] = {}
        if raw_notes:
            try:
                parsed = json.loads(raw_notes) if isinstance(raw_notes, str) else raw_notes
                if isinstance(parsed, dict):
                    notes_payload.update(parsed)
                else:
                    notes_payload["notes_text"] = str(raw_notes)
            except Exception:
                notes_payload["notes_text"] = str(raw_notes)
        # Accepte aussi les champs envoyés directement par la carte Pool House.
        for key in ("brand", "form", "unit_weight_g", "multifunction", "dissolution", "stabilized", "treatment_place", "shock_dose_amount", "initial_dose_amount"):
            if data.get(key) not in (None, ""):
                notes_payload[key] = data.get(key)
        notes = json.dumps(notes_payload, ensure_ascii=False) if notes_payload else None
        category = str(data.get("category") or data.get("product_type") or "other")
        if category == "anti_algae":
            category = "algaecide"
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            name=str(data.get("name") or "Produit"),
            category=category,
            dosage_quantity=float(data.get("dosage_quantity") or data.get("normal_dose_amount") or 0),
            dosage_unit=str(data.get("dosage_unit") or data.get("dose_unit") or data.get("stock_unit") or "g"),
            volume_basis_m3=float(data.get("volume_basis_m3") or data.get("reference_volume_m3") or 10.0),
            effect_delta=float(data["effect_delta"]) if data.get("effect_delta") not in (None, "", 0) else None,
            stock_quantity=float(data["stock_quantity"]) if data.get("stock_quantity") not in (None, "") else None,
            stock_unit=str(data.get("stock_unit") or data.get("unit") or data.get("dosage_unit") or "g"),
            notes=notes,
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
    strip_test: dict[str, Any] = field(default_factory=dict)
    raw_measurements: list[dict[str, Any]] = field(default_factory=list)
    maintenance_journal: list[dict[str, Any]] = field(default_factory=list)
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
    auto_filter_active: bool = False
    auto_filter_end: datetime | None = None
    auto_filter_remaining_hours: float | None = None
    auto_schedule_enabled: bool = False
    auto_schedule_status: str = "disabled"
    auto_schedule_windows: list[dict[str, str]] = field(default_factory=list)
    auto_schedule_next_start: datetime | None = None
    auto_schedule_target_hours: float | None = None
    auto_schedule_done_hours: float | None = None
    auto_schedule_end_limit: str | None = None
    auto_schedule_detail: dict[str, Any] = field(default_factory=dict)

class PoolPilotCoordinator(DataUpdateCoordinator[PoolPilotData]):
    config_entry: ConfigEntry
    _unsubscribe: Callable[[], None] | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.entry_id}", update_interval=None)
        self.config_entry = entry
        self._last_product_confirmed: str | None = None
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self.products: dict[str, ChemicalProduct] = {}
        self._auto_filter_unsub: Callable[[], None] | None = None
        self._auto_filter_start: datetime | None = None
        self._auto_filter_end: datetime | None = None
        self._auto_schedule_enabled: bool = False
        self._auto_schedule_unsub: Callable[[], None] | None = None
        self._auto_schedule_owns_pump: bool = False
        self.strip_test: dict[str, Any] = {}
        self.raw_measurements: list[dict[str, Any]] = []
        self.maintenance_journal: list[dict[str, Any]] = []
        self._auto_schedule_day = None
        self._auto_schedule_seconds_today: float = 0.0
        self._auto_schedule_last_tick: datetime | None = None

    @property
    def pool_name(self) -> str:
        return str(self.config_entry.data.get(CONF_POOL_NAME, "Piscine"))

    def option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    async def async_setup(self) -> None:
        await self.async_load_products()
        await self.async_load_scheduler_state()
        entities = [self.config_entry.data.get(k) for k in (
            CONF_TEMP_ENTITY, CONF_PH_ENTITY, CONF_ORP_ENTITY, CONF_FC_ENTITY, CONF_TA_ENTITY,
            CONF_CH_ENTITY, CONF_CYA_ENTITY, CONF_SALT_ENTITY, CONF_PUMP_SWITCH, CONF_HEATPUMP_ENTITY,
            CONF_WEATHER_ENTITY, CONF_FORECAST_TEMP_ENTITY, CONF_COVER_ENTITY)]
        entities = [e for e in entities if e]
        if entities:
            self._unsubscribe = async_track_state_change_event(self.hass, entities, self._async_state_changed)
        self._auto_schedule_unsub = async_track_time_interval(self.hass, self._async_auto_schedule_tick, timedelta(minutes=1))
        await self.async_request_refresh()
        await self._async_auto_schedule_tick(dt_util.now())

    def async_shutdown(self) -> None:
        if self._unsubscribe:
            self._unsubscribe(); self._unsubscribe = None
        if self._auto_filter_unsub:
            self._auto_filter_unsub(); self._auto_filter_unsub = None
        if self._auto_schedule_unsub:
            self._auto_schedule_unsub(); self._auto_schedule_unsub = None

    async def async_load_products(self) -> None:
        stored = await self._store.async_load() or {}
        self.products = {p.id: p for p in [ChemicalProduct.from_dict(x) for x in stored.get("products", [])]}
        self.strip_test = dict(stored.get("strip_test", {}))
        self.raw_measurements = list(stored.get("raw_measurements", []))
        self.maintenance_journal = list(stored.get("maintenance_journal", []))

    async def async_load_scheduler_state(self) -> None:
        stored = await self._store.async_load() or {}
        self._auto_schedule_enabled = bool(stored.get("auto_schedule_enabled", False))
        self._auto_schedule_day = stored.get("auto_schedule_day")
        self._auto_schedule_seconds_today = float(stored.get("auto_schedule_seconds_today", 0.0) or 0.0)

    async def async_save_products(self) -> None:
        await self._store.async_save({"products": [p.as_dict() for p in self.products.values()], "auto_schedule_enabled": self._auto_schedule_enabled, "strip_test": self.strip_test, "raw_measurements": self.raw_measurements, "maintenance_journal": self.maintenance_journal, "auto_schedule_day": self._auto_schedule_day, "auto_schedule_seconds_today": self._auto_schedule_seconds_today})
        self.async_set_updated_data(self._calculate())

    async def async_add_product(self, **data: Any) -> str:
        product = ChemicalProduct.from_dict(data)
        self.products[product.id] = product
        await self.async_save_products()
        return product.id

    async def async_update_product(self, **data: Any) -> str:
        """Update an existing Pool House product.

        This is intentionally tolerant: if the product does not exist yet, it is
        created with the supplied id. This allows the Lovelace editor pencil
        button to use a single save action.
        """
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
        self._append_journal_entry("chemical", "Utilisation de produits chimiques", f"Ajout de {self._fmt_quantity(float(quantity), p.dosage_unit)} de {p.name}", product_id=p.id, product_name=p.name, quantity=float(quantity), unit=p.dosage_unit)
        await self.async_save_products()

    def confirm_product(self, category: str) -> None:
        rec = self._first_recommendation_for_category(category)
        if rec:
            self.hass.async_create_task(self.async_confirm_product_added(rec.product_id, rec.quantity))
        else:
            self._last_product_confirmed = f"{category} à {dt_util.now().strftime('%Y-%m-%d %H:%M')}"
            self.async_set_updated_data(self._calculate())



    def _journal_label(self, category: str) -> str:
        labels = {
            "water_quality": "Qualité de l'eau",
            "strip_test": "Nouveau test de bandelettes",
            "chemical": "Utilisation de produits chimiques",
            "stock": "Gestion des stocks",
            "equipment": "Nouvel équipement",
            "maintenance": "Entretien",
            "cleaning": "Nettoyage",
            "filter": "Lavage filtre",
            "drain": "Vidange de la piscine",
            "weather": "Événement climatique",
            "filtration": "Filtration",
            "note": "Note",
            "alert": "Alerte",
        }
        return labels.get(category, category or "Note")

    def _journal_color(self, category: str) -> str:
        colors = {
            "alert": "#ff1515",
            "water_quality": "#ff1515",
            "chemical": "#459be8",
            "stock": "#c414d9",
            "strip_test": "#2fcbd0",
            "equipment": "#b914d9",
            "maintenance": "#b914d9",
            "cleaning": "#b914d9",
            "filter": "#b914d9",
            "drain": "#2ea8df",
            "weather": "#f59f18",
            "filtration": "#2fcbd0",
            "note": "#64748b",
        }
        return colors.get(category, "#64748b")

    def _journal_icon(self, category: str) -> str:
        icons = {
            "alert": "mdi:close",
            "water_quality": "mdi:close",
            "chemical": "mdi:bottle-tonic-outline",
            "stock": "mdi:package-variant-closed",
            "strip_test": "mdi:test-tube",
            "equipment": "mdi:tools",
            "maintenance": "mdi:tools",
            "cleaning": "mdi:broom",
            "filter": "mdi:filter-outline",
            "drain": "mdi:water-percent",
            "weather": "mdi:weather-lightning",
            "filtration": "mdi:sync",
            "note": "mdi:note-text-outline",
        }
        return icons.get(category, "mdi:note-text-outline")

    def _append_journal_entry(self, category: str, title: str | None = None, description: str | None = None, **extra: Any) -> str:
        now = dt_util.now()
        entry_id = str(extra.pop("id", None) or uuid.uuid4().hex[:10])
        category = category or "note"
        entry = {
            "id": entry_id,
            "date": now.isoformat(),
            "datetime": now.strftime("%d/%m %H:%M"),
            "category": category,
            "category_label": self._journal_label(category),
            "title": title or self._journal_label(category),
            "description": description or "",
            "icon": self._journal_icon(category),
            "color": self._journal_color(category),
            **{k: v for k, v in extra.items() if v is not None},
        }
        self.maintenance_journal.insert(0, entry)
        self.maintenance_journal = self.maintenance_journal[:250]
        return entry_id

    async def async_add_journal_entry(self, **data: Any) -> str:
        category = str(data.get("category") or "note")
        title = data.get("title") or self._journal_label(category)
        description = data.get("description") or data.get("comment") or ""
        extra = {k: v for k, v in data.items() if k not in ("category", "title", "description", "comment")}
        entry_id = self._append_journal_entry(category, str(title), str(description), **extra)
        await self.async_save_products()
        return entry_id

    async def async_remove_journal_entry(self, entry_id: str) -> None:
        self.maintenance_journal = [e for e in self.maintenance_journal if str(e.get("id")) != str(entry_id)]
        await self.async_save_products()

    async def async_update_strip_test(self, **data: Any) -> None:
        """Save a manual strip-test / expert-mode measurement.

        The strip test is stored persistently in the integration Store, exposed
        through sensor.pool_pilot_strip_test attributes, and reused by Pool Pilot
        calculations for manual-only values such as TAC/TH/CYA.

        Live sensors remain the priority for pH / free chlorine when configured.
        Strip pH / free chlorine are used as fallback values when no live entity is
        available.
        """
        now = dt_util.now()

        aliases = {
            "ph": ("ph", "strip_ph"),
            "alkalinity": ("alkalinity", "tac", "strip_alkalinity"),
            "calcium": ("calcium", "hardness", "th", "strip_calcium"),
            "cya": ("cya", "stabilizer", "stabilisant", "strip_cya"),
            "free_chlorine": ("free_chlorine", "chlorine_free", "chlore_libre", "strip_free_chlorine"),
            "total_chlorine": ("total_chlorine", "chlorine_total", "chlore_total", "strip_total_chlorine"),
            "temperature": ("temperature", "temp", "strip_temperature"),
        }

        cleaned: dict[str, Any] = {
            "updated_at": now.isoformat(),
            "updated_at_local": now.strftime("%d/%m/%Y %H:%M"),
            "source": "strip_test",
        }

        for target, keys in aliases.items():
            value = None
            for key in keys:
                if data.get(key) not in (None, ""):
                    value = data.get(key)
                    break
            if value not in (None, ""):
                try:
                    cleaned[target] = float(value)
                except (TypeError, ValueError):
                    pass

        # Useful display conversions for the dashboard.
        if "alkalinity" in cleaned:
            cleaned["alkalinity_f"] = round(float(cleaned["alkalinity"]) / 10, 1)
        if "calcium" in cleaned:
            cleaned["calcium_f"] = round(float(cleaned["calcium"]) / 10, 1)

        self.strip_test.update(cleaned)

        row = {
            "datetime": now.strftime("%d/%m %H:%M"),
            "source": "strip_test",
            "ph": cleaned.get("ph", self._float(self.config_entry.data.get(CONF_PH_ENTITY))),
            "orp": self._float(self.config_entry.data.get(CONF_ORP_ENTITY)),
            "temp": cleaned.get("temperature", self._temp_c(self.config_entry.data.get(CONF_TEMP_ENTITY))),
            "alkalinity": cleaned.get("alkalinity"),
            "calcium": cleaned.get("calcium"),
            "cya": cleaned.get("cya"),
            "free_chlorine": cleaned.get("free_chlorine"),
            "total_chlorine": cleaned.get("total_chlorine"),
        }
        self.raw_measurements.insert(0, row)
        self.raw_measurements = self.raw_measurements[:50]
        details = []
        for label, key, unit in (
            ("pH", "ph", ""),
            ("TAC", "alkalinity", " ppm"),
            ("TH", "calcium", " ppm"),
            ("Stabilisant", "cya", " ppm"),
            ("Chlore libre", "free_chlorine", " ppm"),
            ("Chlore total", "total_chlorine", " ppm"),
            ("Température", "temperature", " °C"),
        ):
            if key in cleaned:
                details.append(f"{label}: {cleaned[key]}{unit}")
        self._append_journal_entry("strip_test", "Nouveau test de bandelettes", " · ".join(details), values=dict(cleaned))
        await self.async_save_products()

    async def async_set_auto_schedule_enabled(self, enabled: bool) -> None:
        """Enable or disable the daily recommended filtration planner."""
        self._auto_schedule_enabled = bool(enabled)
        if not self._auto_schedule_enabled:
            await self._async_scheduler_turn_pump_off_if_owned()
        await self.async_save_products()
        await self._async_auto_schedule_tick(dt_util.now())

    async def async_toggle_auto_schedule(self) -> None:
        await self.async_set_auto_schedule_enabled(not self._auto_schedule_enabled)

    def _parse_time_option(self, key: str, default: str) -> tuple[int, int]:
        """Parse HH:MM option safely."""
        raw = str(self.option(key, default) or default).strip()
        try:
            hour, minute = raw.split(":", 1)
            h = max(0, min(23, int(hour)))
            m = max(0, min(59, int(minute)))
            return h, m
        except Exception:
            h, m = default.split(":", 1)
            return int(h), int(m)

    def _allowed_window_today(self) -> tuple[datetime, datetime]:
        now = dt_util.now()
        today = now.date()
        sh, sm = self._parse_time_option(CONF_AUTO_START_TIME, DEFAULT_AUTO_START_TIME)
        eh, em = self._parse_time_option(CONF_AUTO_END_TIME, DEFAULT_AUTO_END_TIME)
        start = dt_util.as_local(datetime.combine(today, datetime.min.time())).replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = dt_util.as_local(datetime.combine(today, datetime.min.time())).replace(hour=eh, minute=em, second=0, microsecond=0)
        if end <= start:
            end = start + timedelta(hours=15)
        return start, end

    def _reset_auto_day_if_needed(self) -> None:
        today = dt_util.now().date().isoformat()
        if self._auto_schedule_day != today:
            self._auto_schedule_day = today
            self._auto_schedule_seconds_today = 0.0
            self._auto_schedule_last_tick = None
            self._auto_schedule_owns_pump = False

    def _auto_schedule_target_hours(self) -> float:
        """Return the smart daily target, capped to the configured allowed window."""
        data = self.data or self._calculate()
        target = float(data.recommended_filter_hours or 0.0)
        start, end = self._allowed_window_today()
        max_window = max(0.1, (end - start).total_seconds() / 3600)
        return round(max(0.0, min(target, max_window)), 2)

    def _today_schedule_windows(self) -> list[tuple[datetime, datetime]]:
        """Auto intelligent uses one allowed daily window.

        The pump starts at the beginning of the window, or immediately when the
        mode is enabled inside the window, then stops when the smart daily target
        is reached or at the end limit.
        """
        start, end = self._allowed_window_today()
        return [(start, end)]

    def _schedule_windows_as_dicts(self) -> list[dict[str, str]]:
        done = round(self._auto_schedule_seconds_today / 3600, 2)
        target = self._auto_schedule_target_hours()
        return [{"start": s.isoformat(), "end": e.isoformat(), "label": f"{s.strftime('%H:%M')} → {e.strftime('%H:%M')}", "target_hours": target, "done_hours": done} for s, e in self._today_schedule_windows()]

    def _next_schedule_start(self) -> datetime | None:
        if not self._auto_schedule_enabled:
            return None
        self._reset_auto_day_if_needed()
        now = dt_util.now()
        start, end = self._allowed_window_today()
        target = self._auto_schedule_target_hours()
        done = self._auto_schedule_seconds_today / 3600
        if now < start and done < target:
            return start
        if start <= now < end and done < target:
            return now
        return start + timedelta(days=1)

    async def _async_scheduler_turn_pump_off_if_owned(self) -> None:
        pump = self.config_entry.data.get(CONF_PUMP_SWITCH)
        if pump and self._auto_schedule_owns_pump:
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": pump}, blocking=True)
        self._auto_schedule_owns_pump = False

    async def _async_auto_schedule_tick(self, now: datetime) -> None:
        """Auto intelligent daily filtration.

        Enabled once, it runs every day between 07:00 and 22:00 by default,
        until the smart target computed from water temperature and weather is met.
        """
        pump = self.config_entry.data.get(CONF_PUMP_SWITCH)
        if not pump:
            return
        self._reset_auto_day_if_needed()
        now = dt_util.as_local(now)
        start, end = self._allowed_window_today()
        target_hours = self._auto_schedule_target_hours()
        done_hours = self._auto_schedule_seconds_today / 3600
        pump_is_on = self._is_on(pump)

        if self._auto_schedule_enabled and self._auto_schedule_last_tick and pump_is_on is True and start <= now <= end:
            delta = max(0, min(120, (now - self._auto_schedule_last_tick).total_seconds()))
            self._auto_schedule_seconds_today += delta
            done_hours = self._auto_schedule_seconds_today / 3600
        self._auto_schedule_last_tick = now

        should_run = bool(self._auto_schedule_enabled and start <= now < end and done_hours < target_hours)
        if should_run and pump_is_on is not True:
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": pump}, blocking=True)
            self._auto_schedule_owns_pump = True
        elif (not should_run) and self._auto_schedule_owns_pump:
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": pump}, blocking=True)
            self._auto_schedule_owns_pump = False
        self.async_set_updated_data(self._calculate())

    async def async_start_auto_filter(self, duration_hours: float | None = None) -> None:
        """Start pump for the recommended filtration duration, then stop it automatically."""
        pump = self.config_entry.data.get(CONF_PUMP_SWITCH)
        if not pump:
            raise ValueError("Aucune entité pompe configurée")
        data = self.data or self._calculate()
        hours = float(duration_hours or data.recommended_filter_hours or 0)
        min_h = float(self.option(CONF_MIN_FILTER_HOURS, DEFAULT_MIN_FILTER_HOURS))
        max_h = float(self.option(CONF_MAX_FILTER_HOURS, DEFAULT_MAX_FILTER_HOURS))
        hours = max(0.1, min(max_h, max(hours, min_h)))

        if self._auto_filter_unsub:
            self._auto_filter_unsub()
            self._auto_filter_unsub = None

        self._auto_filter_start = dt_util.now()

        # Auto intelligent: ne jamais démarrer après l'heure de fin autorisée (22h par défaut)
        end_cfg = self.option(CONF_AUTO_END_TIME, DEFAULT_AUTO_END_TIME)
        try:
            end_hour, end_min = [int(x) for x in str(end_cfg).split(":")]
            now = self._auto_filter_start
            if (now.hour, now.minute) >= (end_hour, end_min):
                self._auto_filter_end = None
                await self.async_request_refresh()
                return
        except Exception:
            pass

        self._auto_filter_end = self._auto_filter_start + timedelta(hours=hours)
        await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": pump}, blocking=True)

        async def _finish(now: datetime) -> None:
            self._auto_filter_unsub = None
            self._auto_filter_start = None
            self._auto_filter_end = None
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": pump}, blocking=True)
            await self.async_request_refresh()

        self._auto_filter_unsub = async_call_later(self.hass, hours * 3600, _finish)
        await self.async_request_refresh()

    async def async_stop_auto_filter(self, turn_off: bool = True) -> None:
        """Cancel automatic filtration and optionally stop the pump."""
        if self._auto_filter_unsub:
            self._auto_filter_unsub()
            self._auto_filter_unsub = None
        self._auto_filter_start = None
        self._auto_filter_end = None
        pump = self.config_entry.data.get(CONF_PUMP_SWITCH)
        if turn_off and pump:
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": pump}, blocking=True)
        await self.async_request_refresh()

    def _auto_filter_remaining_hours(self) -> float | None:
        if not self._auto_filter_end:
            return None
        remaining = (self._auto_filter_end - dt_util.now()).total_seconds() / 3600
        return round(max(0.0, remaining), 2)

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

    def _weather_forecast_temp(self) -> float | None:
        entity_id = self.config_entry.data.get(CONF_WEATHER_ENTITY)
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if not st:
            return None
        # Prefer max forecast temperature from attributes if available; otherwise
        # use current weather temperature as a conservative proxy.
        forecasts = st.attributes.get("forecast") or []
        temps: list[float] = []
        if isinstance(forecasts, list):
            for item in forecasts[:8]:
                if isinstance(item, dict):
                    for key in ("temperature", "templow", "native_temperature"):
                        val = item.get(key)
                        try:
                            if val is not None:
                                temps.append(float(val))
                        except (TypeError, ValueError):
                            pass
        for key in ("temperature", "native_temperature"):
            val = st.attributes.get(key)
            try:
                if val is not None:
                    temps.append(float(val))
            except (TypeError, ValueError):
                pass
        if not temps:
            return None
        val = max(temps)
        unit = st.attributes.get("temperature_unit") or st.attributes.get("unit_of_measurement")
        if unit == UnitOfTemperature.FAHRENHEIT or unit == "°F":
            return (val - 32) * 5 / 9
        return val

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

    def _strip_or_entity_float(self, strip_key: str, entity_id: str | None, prefer_strip: bool = False) -> float | None:
        """Return a value from strip test or live entity.

        For automatically measured values, live entity wins by default.
        For manual-only values such as TAC/TH/CYA, strip wins.
        """
        strip_value = self.strip_test.get(strip_key)
        entity_value = self._float(entity_id)
        if prefer_strip:
            return strip_value if strip_value is not None else entity_value
        return entity_value if entity_value is not None else strip_value

    def _calculate(self) -> PoolPilotData:
        d = self.config_entry.data
        temp = self._temp_c(d.get(CONF_TEMP_ENTITY))
        forecast = self._weather_forecast_temp() or self._temp_c(d.get(CONF_FORECAST_TEMP_ENTITY))
        ph = self._strip_or_entity_float("ph", d.get(CONF_PH_ENTITY), prefer_strip=False)
        orp = self._float(d.get(CONF_ORP_ENTITY))
        fc = self._strip_or_entity_float("free_chlorine", d.get(CONF_FC_ENTITY), prefer_strip=False)
        ta = self._strip_or_entity_float("alkalinity", d.get(CONF_TA_ENTITY), prefer_strip=True)
        ch = self._strip_or_entity_float("calcium", d.get(CONF_CH_ENTITY), prefer_strip=True)
        cya = self._strip_or_entity_float("cya", d.get(CONF_CYA_ENTITY), prefer_strip=True)
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
        
        auto_remaining = self._auto_filter_remaining_hours()
        auto_active = auto_remaining is not None and auto_remaining > 0
        schedule_windows = self._schedule_windows_as_dicts() if self._auto_schedule_enabled else []
        schedule_next = self._next_schedule_start() if self._auto_schedule_enabled else None
        schedule_target = self._auto_schedule_target_hours() if self._auto_schedule_enabled else None
        schedule_done = round(self._auto_schedule_seconds_today / 3600, 2) if self._auto_schedule_enabled else None
        start, end = self._allowed_window_today()
        schedule_status = "disabled"
        if self._auto_schedule_enabled:
            now = dt_util.now()
            if schedule_target is not None and schedule_done is not None and schedule_done >= schedule_target:
                schedule_status = "done"
            elif start <= now < end and pump_on is True:
                schedule_status = "running"
            else:
                schedule_status = "waiting"
            actions.insert(0, f"Filtration intelligente: {schedule_done or 0} h / {schedule_target or 0} h")
        if auto_active:
            actions.insert(0, f"Filtration auto en cours: {auto_remaining} h restantes")
        detail = {"mode": "auto_intelligent", "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M"), "water_temp_c": temp, "forecast_temp_c": forecast, "weather_factor": weather_factor, "base_hours": round((temp / float(self.option(CONF_FILTER_COEF, DEFAULT_FILTER_COEF))), 2) if temp is not None else None}
        return PoolPilotData(
            water_temp_c=temp,
            ph=ph,
            orp=orp,
            free_chlorine=fc,
            alkalinity=ta,
            calcium=ch,
            cya=cya,
            salt=salt,
            strip_test=dict(self.strip_test),
            raw_measurements=list(self.raw_measurements),
            maintenance_journal=list(self.maintenance_journal),
            forecast_temp_c=forecast,
            pump_on=pump_on,
            heatpump_on=hp_on,
            cover_closed=cover,
            recommended_filter_hours=hours,
            weather_factor=weather_factor,
            chemistry_status=chemistry_status,
            bathing_status=bathing,
            action_summary=" · ".join(actions) if actions else "Aucune action",
            alerts=alerts,
            recommendations=recs,
            products=list(self.products.values()),
            last_product_confirmed=self._last_product_confirmed,
            last_updated=dt_util.now(),
            auto_filter_active=auto_active,
            auto_filter_end=self._auto_filter_end,
            auto_filter_remaining_hours=auto_remaining,
            auto_schedule_enabled=self._auto_schedule_enabled,
            auto_schedule_status=schedule_status,
            auto_schedule_windows=schedule_windows,
            auto_schedule_next_start=schedule_next,
            auto_schedule_target_hours=schedule_target,
            auto_schedule_done_hours=schedule_done,
            auto_schedule_end_limit=end.strftime("%H:%M"),
            auto_schedule_detail=detail,
        )
