"""Water-balance recommendation engine v2 for Pool Pilot.

This module deliberately sits beside the historical coordinator so the water
balance decision rules can evolve without making coordinator.py even larger.
It is installed once when the integration package is imported and overrides
only the recommendation-related coordinator methods.

Scope of this first v2 step:
- pH operational/optimal zones instead of chasing an exact setpoint;
- treatment-aware TAC targets;
- calcium-hardness/LSI arbitration;
- one structural correction at a time;
- no fabricated product effect when manufacturer data is missing;
- correction hold after a confirmed chemical addition;
- LSI balanced zone widened to -0.20..+0.20.

Disinfection (CYA/free chlorine/ORP) remains delegated to the historical
engine for now and will be migrated in the next v2 step.
"""
from __future__ import annotations

from datetime import timedelta
import json
import math
from typing import Any

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CH_ENTITY,
    CONF_ORP_ENTITY,
    CONF_PH_ENTITY,
    CONF_TA_ENTITY,
    CONF_TARGET_FC,
    CONF_TARGET_ORP,
    CONF_TARGET_PH,
    CONF_VOLUME_M3,
    DEFAULT_TARGET_FC,
    DEFAULT_TARGET_ORP,
    DEFAULT_TARGET_PH,
    DOMAIN,
    MEASUREMENT_MODE_ORP,
    POOL_TYPE_ACTIVE_OXYGEN,
    POOL_TYPE_BROMINE,
    POOL_TYPE_CHLORINE,
    POOL_TYPE_SALT,
)

PH_OPTIMAL_MIN = 7.20
PH_OPTIMAL_MAX = 7.60
PH_OPERATIONAL_MIN = 7.00
PH_OPERATIONAL_MAX = 7.80

TA_GENERAL_LOW = 60.0
TA_GENERAL_HIGH = 180.0
TA_TARGET_LOW = 80.0
TA_TARGET_HIGH = 120.0

CALCIUM_OPTIMAL_MIN = 200.0
CALCIUM_OPTIMAL_MAX = 400.0
CALCIUM_VERY_LOW = 150.0
CALCIUM_HIGH = 600.0

LSI_BALANCED_MIN = -0.20
LSI_BALANCED_MAX = 0.20
LSI_STRONG_LOW = -0.50
LSI_STRONG_HIGH = 0.50

CORRECTION_STORAGE_VERSION = 1
CORRECTION_STORAGE_PREFIX = f"{DOMAIN}_recommendation_v2"

MINERAL_SURFACES = {"concrete", "tile", "painted"}


def _product_notes(product: Any) -> dict[str, Any]:
    raw = getattr(product, "notes", None)
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _stock_after(product: Any, quantity: float) -> float | None:
    stock = getattr(product, "stock_quantity", None)
    if stock is None:
        return None
    if getattr(product, "stock_unit", None) != getattr(product, "dosage_unit", None):
        return None
    return float(stock) - float(quantity)


def _manufacturer_quantity(coordinator: Any, product: Any, desired_delta: float) -> float | None:
    """Return a dose only when the product declares a usable effect_delta.

    effect_delta is interpreted as the change produced by dosage_quantity for
    volume_basis_m3. No fallback effect is invented. An optional
    max_single_dose_amount stored in product notes can cap the immediate dose.
    """
    try:
        effect = abs(float(product.effect_delta)) if product.effect_delta is not None else 0.0
        if effect <= 0 or desired_delta <= 0:
            return None
        volume = float(coordinator.config_entry.data.get(CONF_VOLUME_M3) or 0)
        basis = float(product.volume_basis_m3 or 0)
        base_qty = float(product.dosage_quantity or 0)
        if volume <= 0 or basis <= 0 or base_qty <= 0:
            return None
        steps = abs(float(desired_delta)) / effect
        theoretical = base_qty * (volume / basis) * steps
        notes = _product_notes(product)
        max_single = notes.get("max_single_dose_amount")
        if max_single not in (None, ""):
            try:
                theoretical = min(theoretical, max(0.0, float(max_single)))
            except (TypeError, ValueError):
                pass
        return round(max(0.0, theoretical), 2)
    except Exception:
        return None


def _ph_state(ph: float | None) -> str:
    if ph is None:
        return "unknown"
    if PH_OPTIMAL_MIN <= ph <= PH_OPTIMAL_MAX:
        return "optimal"
    if PH_OPERATIONAL_MIN <= ph <= PH_OPERATIONAL_MAX:
        return "watch"
    return "correct"


def _ta_target(coordinator: Any) -> tuple[float, float, float]:
    """Return preferred low/high/center TAC target for the configured treatment."""
    pool_type = coordinator._pool_type()
    if pool_type == POOL_TYPE_SALT:
        return 80.0, 100.0, 90.0
    if pool_type in (POOL_TYPE_BROMINE, POOL_TYPE_ACTIVE_OXYGEN):
        return 80.0, 120.0, 100.0

    # Traditional chlorine: if the user's primary maintenance product is marked
    # stabilized (or is a slow chlorine tablet), prefer the slightly higher TAC
    # band used with acidifying stabilized chlorine. Otherwise use 80-100 ppm.
    preferred = coordinator._preferred_disinfection_product()
    notes = _product_notes(preferred) if preferred is not None else {}
    stabilized = bool(notes.get("stabilized"))
    category = str(getattr(preferred, "category", "") or "")
    if stabilized or category == "chlorine_slow":
        return 100.0, 120.0, 110.0
    return 80.0, 100.0, 90.0


def _water_balance_context(coordinator: Any) -> dict[str, Any]:
    d = coordinator.config_entry.data
    ph = coordinator._strip_or_entity_float("ph", d.get(CONF_PH_ENTITY), prefer_strip=False)
    ta = coordinator._strip_or_entity_float("alkalinity", d.get(CONF_TA_ENTITY), prefer_strip=True)
    calcium = coordinator._strip_or_entity_float("calcium", d.get(CONF_CH_ENTITY), prefer_strip=True)
    temp = coordinator._temp_c(d.get("temp_entity"))
    salt = coordinator._float(d.get("salt_entity"))
    lsi, lsi_status, *_ = coordinator._lsi(ph, temp, ta, calcium, salt)
    ta_low, ta_high, ta_center = _ta_target(coordinator)
    surface = str(d.get("surface_type") or "other").lower()
    return {
        "ph": ph,
        "ph_state": _ph_state(ph),
        "ta": ta,
        "ta_target_low": ta_low,
        "ta_target_high": ta_high,
        "ta_target_center": ta_center,
        "calcium": calcium,
        "lsi": lsi,
        "lsi_status": lsi_status,
        "surface": surface,
        "calcium_basis": "calcium_hardness_ppm_caco3",
    }


def _active_correction(coordinator: Any) -> tuple[Any | None, str | None]:
    until = getattr(coordinator, "_recommendation_v2_correction_until", None)
    summary = getattr(coordinator, "_recommendation_v2_correction_summary", None)
    if until is None:
        return None, None
    try:
        if dt_util.now() < until:
            return until, summary
    except Exception:
        pass
    coordinator._recommendation_v2_correction_until = None
    coordinator._recommendation_v2_correction_summary = None
    coordinator._recommendation_v2_correction_category = None
    return None, None


def _structural_recommendation(coordinator: Any, ProductRecommendation: Any) -> Any | None:
    """Return at most one high-priority pH/TAC/calcium recommendation."""
    ctx = _water_balance_context(coordinator)
    ph = ctx["ph"]
    ta = ctx["ta"]
    calcium = ctx["calcium"]
    lsi = ctx["lsi"]

    if ph is not None and (ph < 5.5 or ph > 9.0):
        # Extreme/suspicious pH: do not output a chemical dose from one reading.
        return None

    # Low pH + severely low buffering capacity: stabilize TAC first.
    if ph is not None and ph < PH_OPERATIONAL_MIN and ta is not None and ta < TA_GENERAL_LOW:
        product = coordinator._best_product("alkalinity")
        if product is not None:
            qty = _manufacturer_quantity(coordinator, product, ctx["ta_target_center"] - ta)
            if qty is not None and qty > 0:
                return ProductRecommendation(
                    product.id, product.name, product.category, qty, product.dosage_unit,
                    f"pH {ph:.2f} et TAC {ta:.0f} ppm : corriger d'abord le pouvoir tampon avant de réévaluer le pH.",
                    aftercare="Laissez circuler l'eau puis refaites une mesure pH/TAC avant toute autre correction.",
                    stock_after=_stock_after(product, qty), stock_unit=product.stock_unit,
                )

    # pH: trigger only outside the operational 7.0-7.8 envelope. The configured
    # setpoint remains the calculation target but is clamped to the optimal band.
    if ph is not None and ph > PH_OPERATIONAL_MAX:
        product = coordinator._best_product("ph_minus")
        if product is not None:
            target = min(PH_OPTIMAL_MAX, max(PH_OPTIMAL_MIN, float(coordinator.option(CONF_TARGET_PH, DEFAULT_TARGET_PH))))
            qty = _manufacturer_quantity(coordinator, product, ph - target)
            if qty is not None and qty > 0:
                reason = f"pH {ph:.2f} hors plage opérationnelle; cible de correction {target:.2f}."
                if ta is not None and ta > TA_GENERAL_HIGH:
                    reason += f" TAC élevé ({ta:.0f} ppm), correction à réaliser progressivement."
                return ProductRecommendation(
                    product.id, product.name, product.category, qty, product.dosage_unit, reason,
                    aftercare="Dose calculée à partir des données fabricant. Respectez la dose maximale de la notice, laissez circuler puis recontrôlez avant une nouvelle correction.",
                    stock_after=_stock_after(product, qty), stock_unit=product.stock_unit,
                )

    if ph is not None and ph < PH_OPERATIONAL_MIN:
        product = coordinator._best_product("ph_plus")
        if product is not None:
            target = min(PH_OPTIMAL_MAX, max(PH_OPTIMAL_MIN, float(coordinator.option(CONF_TARGET_PH, DEFAULT_TARGET_PH))))
            qty = _manufacturer_quantity(coordinator, product, target - ph)
            if qty is not None and qty > 0:
                return ProductRecommendation(
                    product.id, product.name, product.category, qty, product.dosage_unit,
                    f"pH {ph:.2f} hors plage opérationnelle; cible de correction {target:.2f}.",
                    aftercare="Dose calculée à partir des données fabricant. Laissez circuler puis recontrôlez avant une nouvelle correction.",
                    stock_after=_stock_after(product, qty), stock_unit=product.stock_unit,
                )

    # TAC is corrected only when it leaves the broad 60-180 ppm envelope.
    if ta is not None and ta < TA_GENERAL_LOW:
        product = coordinator._best_product("alkalinity")
        if product is not None:
            qty = _manufacturer_quantity(coordinator, product, ctx["ta_target_center"] - ta)
            if qty is not None and qty > 0:
                return ProductRecommendation(
                    product.id, product.name, product.category, qty, product.dosage_unit,
                    f"TAC très bas ({ta:.0f} ppm); cible préférentielle {ctx['ta_target_low']:.0f}-{ctx['ta_target_high']:.0f} ppm pour ce traitement.",
                    aftercare="Corrigez progressivement, laissez circuler puis refaites un test pH/TAC avant toute autre correction.",
                    stock_after=_stock_after(product, qty), stock_unit=product.stock_unit,
                )

    # Calcium hardness is not chased toward 200 ppm by itself. Only a very low
    # value combined with a negative LSI justifies an automatic product proposal.
    if calcium is not None and calcium < CALCIUM_VERY_LOW and lsi is not None and lsi < LSI_BALANCED_MIN:
        surface = ctx["surface"]
        if surface in MINERAL_SURFACES or lsi < LSI_STRONG_LOW:
            product = coordinator._best_product("hardness_plus")
            if product is not None:
                qty = _manufacturer_quantity(coordinator, product, CALCIUM_OPTIMAL_MIN - calcium)
                if qty is not None and qty > 0:
                    return ProductRecommendation(
                        product.id, product.name, product.category, qty, product.dosage_unit,
                        f"Dureté calcique basse ({calcium:.0f} ppm CaCO₃) avec LSI {lsi:+.2f}; correction progressive recommandée.",
                        aftercare="Laissez circuler puis contrôlez de nouveau la dureté calcique, le pH, le TAC et le LSI.",
                        stock_after=_stock_after(product, qty), stock_unit=product.stock_unit,
                    )
    return None


def _advisory_recommendation(coordinator: Any, TreatmentRecommendation: Any) -> Any | None:
    ctx = _water_balance_context(coordinator)
    ph = ctx["ph"]
    ta = ctx["ta"]
    calcium = ctx["calcium"]
    lsi = ctx["lsi"]
    treatment = coordinator._pool_type()

    if ph is not None and (ph < 5.5 or ph > 9.0):
        return TreatmentRecommendation(
            action="verify_measurement", title="Mesure pH à confirmer",
            message=f"pH {ph:.2f} très éloigné de la plage normale : confirmez la mesure avant d'ajouter un produit.",
            treatment=treatment, icon="mdi:test-tube",
        )

    if ph is not None and ph < PH_OPERATIONAL_MIN and ta is not None and ta < TA_GENERAL_LOW:
        product = coordinator._best_product("alkalinity")
        if product is None or _manufacturer_quantity(coordinator, product, ctx["ta_target_center"] - ta) is None:
            return TreatmentRecommendation(
                action="water_balance_tac", title="TAC à corriger en priorité",
                message=f"TAC {ta:.0f} ppm et pH {ph:.2f}. Corrigez d'abord le TAC; dosage indisponible tant que l'effet fabricant du produit n'est pas renseigné.",
                treatment=treatment, icon="mdi:flask-outline",
            )

    if ph is not None and (ph < PH_OPERATIONAL_MIN or ph > PH_OPERATIONAL_MAX):
        category = "ph_plus" if ph < PH_OPERATIONAL_MIN else "ph_minus"
        product = coordinator._best_product(category)
        target = min(PH_OPTIMAL_MAX, max(PH_OPTIMAL_MIN, float(coordinator.option(CONF_TARGET_PH, DEFAULT_TARGET_PH))))
        delta = abs(ph - target)
        if product is None:
            return TreatmentRecommendation(
                action="water_balance_ph", title="Correction du pH nécessaire",
                message=f"pH {ph:.2f} hors plage. Ajoutez un produit adapté, mais aucun {('pH+' if category == 'ph_plus' else 'pH-')} n'est renseigné dans Pool House.",
                treatment=treatment, icon="mdi:ph",
            )
        if _manufacturer_quantity(coordinator, product, delta) is None:
            return TreatmentRecommendation(
                action="water_balance_ph", title="Correction du pH nécessaire",
                message=f"pH {ph:.2f} hors plage. Le produit {product.name} est connu, mais son effet fabricant n'est pas renseigné : Pool Pilot ne fabrique pas de dosage.",
                treatment=treatment, icon="mdi:ph",
            )

    if ta is not None and ta < TA_GENERAL_LOW:
        product = coordinator._best_product("alkalinity")
        if product is None or _manufacturer_quantity(coordinator, product, ctx["ta_target_center"] - ta) is None:
            return TreatmentRecommendation(
                action="water_balance_tac", title="TAC trop bas",
                message=f"TAC {ta:.0f} ppm. Une correction progressive est recommandée; renseignez l'effet fabricant du TAC+ pour obtenir une dose calculée.",
                treatment=treatment, icon="mdi:flask-outline",
            )

    if ta is not None and ta > TA_GENERAL_HIGH:
        return TreatmentRecommendation(
            action="water_balance_tac_high", title="TAC élevé",
            message=f"TAC {ta:.0f} ppm. Ne corrigez pas automatiquement vers une valeur exacte : tenez compte du pH et du LSI et procédez progressivement.",
            treatment=treatment, icon="mdi:flask-outline",
        )

    if calcium is not None and calcium < CALCIUM_VERY_LOW and lsi is not None and lsi < LSI_BALANCED_MIN:
        product = coordinator._best_product("hardness_plus")
        if product is None or _manufacturer_quantity(coordinator, product, CALCIUM_OPTIMAL_MIN - calcium) is None:
            return TreatmentRecommendation(
                action="water_balance_calcium", title="Dureté calcique basse",
                message=f"{calcium:.0f} ppm CaCO₃ avec LSI {lsi:+.2f}. Une correction peut être pertinente, mais aucun dosage fiable n'est disponible dans Pool House.",
                treatment=treatment, icon="mdi:water-outline",
            )

    if calcium is not None and calcium > CALCIUM_HIGH and lsi is not None and lsi > LSI_BALANCED_MAX:
        return TreatmentRecommendation(
            action="water_balance_calcium_high", title="Dureté calcique élevée",
            message=f"{calcium:.0f} ppm CaCO₃ avec LSI {lsi:+.2f}. Évitez une correction produit automatique; contrôlez pH/TAC et envisagez une dilution si nécessaire.",
            treatment=treatment, icon="mdi:water-alert-outline",
        )
    return None


def install_recommendation_engine_v2(CoordinatorClass: Any) -> None:
    """Install the v2 water-balance rules on PoolPilotCoordinator once."""
    if getattr(CoordinatorClass, "_recommendation_engine_v2_installed", False):
        return

    from .coordinator import ProductRecommendation, TreatmentRecommendation

    original_build_recommendations = CoordinatorClass._build_recommendations
    original_build_treatment_recommendations = CoordinatorClass._build_treatment_recommendations
    original_confirm_product = CoordinatorClass.async_confirm_product_added
    original_load_products = CoordinatorClass.async_load_products
    original_calculate = CoordinatorClass._calculate

    def _correction_store(self: Any) -> Store:
        store = getattr(self, "_recommendation_v2_store", None)
        if store is None:
            store = Store(
                self.hass,
                CORRECTION_STORAGE_VERSION,
                f"{CORRECTION_STORAGE_PREFIX}_{self.config_entry.entry_id}",
            )
            self._recommendation_v2_store = store
        return store

    async def async_load_products_v2(self: Any) -> None:
        await original_load_products(self)
        try:
            payload = await _correction_store(self).async_load() or {}
            raw_until = payload.get("correction_until")
            until = dt_util.parse_datetime(raw_until) if raw_until else None
            if until is not None:
                until = dt_util.as_local(until)
            self._recommendation_v2_correction_until = until
            self._recommendation_v2_correction_summary = payload.get("correction_summary")
            self._recommendation_v2_correction_category = payload.get("correction_category")
            _active_correction(self)
        except Exception:
            self._recommendation_v2_correction_until = None
            self._recommendation_v2_correction_summary = None
            self._recommendation_v2_correction_category = None

    async def async_confirm_product_added_v2(self: Any, product_id: str, quantity: float | None = None) -> None:
        product = self.products.get(product_id)
        await original_confirm_product(self, product_id, quantity)
        if product is None:
            return
        category = str(getattr(product, "category", "") or "")
        if category in {"ph_minus", "ph_plus", "alkalinity", "alkalinity_minus", "hardness_plus", "hardness_minus"}:
            hold_hours = 4 if category in {"ph_minus", "ph_plus"} else 6
            until = dt_util.now() + timedelta(hours=hold_hours)
            label = {
                "ph_minus": "Correction pH-",
                "ph_plus": "Correction pH+",
                "alkalinity": "Correction TAC+",
                "alkalinity_minus": "Correction TAC",
                "hardness_plus": "Correction dureté calcique",
                "hardness_minus": "Correction dureté calcique",
            }.get(category, "Correction chimique")
            summary = f"{label} confirmée avec {product.name}. Attendre le brassage et une nouvelle mesure avant une autre correction."
            self._recommendation_v2_correction_until = until
            self._recommendation_v2_correction_summary = summary
            self._recommendation_v2_correction_category = category
            try:
                await _correction_store(self).async_save({
                    "correction_until": until.isoformat(),
                    "correction_summary": summary,
                    "correction_category": category,
                })
            except Exception:
                pass
            await self.async_request_refresh()

    def build_recommendations_v2(self: Any, ph: float | None, fc: float | None, orp: float | None, algae_score: float | None = None) -> list[Any]:
        if _active_correction(self)[0] is not None:
            return []

        structural = _structural_recommendation(self, ProductRecommendation)
        if structural is not None:
            return [structural]

        # Preserve the existing disinfection/algae logic for this first v2 step,
        # but remove legacy pH recommendations so pH only follows the new zones.
        legacy = original_build_recommendations(self, ph, fc, orp, algae_score)
        return [r for r in legacy if str(getattr(r, "category", "")) not in {
            "ph_minus", "ph_plus", "alkalinity", "alkalinity_minus", "hardness_plus", "hardness_minus"
        }]

    def build_treatment_recommendations_v2(self: Any, fc: float | None, orp: float | None) -> list[Any]:
        until, summary = _active_correction(self)
        if until is not None:
            return [TreatmentRecommendation(
                action="correction_wait", title="Correction en cours",
                message=summary or "Attendez une nouvelle mesure avant une autre correction.",
                treatment=self._pool_type(), icon="mdi:timer-sand",
            )]

        advisory = _advisory_recommendation(self, TreatmentRecommendation)
        if advisory is not None:
            # A structural water-balance problem must be resolved before a normal
            # disinfection recommendation is presented as the next action.
            return [advisory]
        return original_build_treatment_recommendations(self, fc, orp)

    def chemistry_status_v2(self: Any, ph: float | None, orp: float | None, fc: float | None) -> tuple[str, list[str]]:
        alerts: list[str] = []
        if ph is None and orp is None and fc is None:
            return "unknown", alerts
        status = "ok"

        if ph is not None:
            if ph < PH_OPERATIONAL_MIN:
                alerts.append(f"pH trop bas: {ph:.2f} (plage opérationnelle {PH_OPERATIONAL_MIN:.1f}-{PH_OPERATIONAL_MAX:.1f})")
                status = "warning"
            elif ph > PH_OPERATIONAL_MAX:
                alerts.append(f"pH trop haut: {ph:.2f} (plage opérationnelle {PH_OPERATIONAL_MIN:.1f}-{PH_OPERATIONAL_MAX:.1f})")
                status = "warning"

        mode = self._disinfection_mode()
        if mode == MEASUREMENT_MODE_ORP:
            if orp is not None:
                target_orp = float(self.option(CONF_TARGET_ORP, DEFAULT_TARGET_ORP))
                if orp < target_orp - 50:
                    alerts.append(f"RedOx bas: {orp:.0f} mV, cible {target_orp:.0f} mV")
                    status = "warning"
                elif orp > target_orp + 150:
                    alerts.append(f"RedOx élevé: {orp:.0f} mV, cible {target_orp:.0f} mV")
                    status = "warning"
        elif fc is not None:
            target_fc = float(self.option(CONF_TARGET_FC, DEFAULT_TARGET_FC))
            if fc < target_fc * 0.75:
                alerts.append("Chlore libre bas: désinfection à renforcer")
                status = "warning"
        return status, alerts

    def lsi_v2(self: Any, ph: float | None, temp: float | None, alkalinity: float | None, calcium: float | None, salt: float | None):
        tds, minf = self._mineralization_tds(salt)
        if ph is None or alkalinity is None or calcium is None or alkalinity <= 0 or calcium <= 0:
            _, comment = self._lsi_status_comment("incomplet", None)
            return None, "incomplet", None, minf, tds, comment
        try:
            temp_c = 25.0 if temp is None else float(temp)
            temp_k = temp_c + 273.15
            a = (math.log10(max(tds, 1.0)) - 1.0) / 10.0
            b = -13.12 * math.log10(temp_k) + 34.55
            c = math.log10(max(float(calcium), 1.0)) - 0.4
            d = math.log10(max(float(alkalinity), 1.0))
            phs = round((9.3 + a + b) - (c + d), 2)
            lsi = round(float(ph) - phs, 2)
            if lsi < LSI_STRONG_LOW:
                status = "corrosive"
            elif lsi < LSI_BALANCED_MIN:
                status = "agressive"
            elif lsi <= LSI_BALANCED_MAX:
                status = "equilibree"
            elif lsi <= LSI_STRONG_HIGH:
                status = "entartrante"
            else:
                status = "tres_entartrante"
            _, comment = self._lsi_status_comment(status, lsi)
            return lsi, status, phs, minf, tds, comment
        except Exception:
            _, comment = self._lsi_status_comment("incomplet", None)
            return None, "incomplet", None, minf, tds, comment

    def calculate_v2(self: Any):
        data = original_calculate(self)
        until, summary = _active_correction(self)
        data.correction_active_until = until
        data.correction_summary = summary
        if until is not None:
            data.recommendations = []
            data.treatment_recommendations = [TreatmentRecommendation(
                action="correction_wait", title="Correction en cours",
                message=summary or "Attendez une nouvelle mesure avant une autre correction.",
                treatment=self._pool_type(), icon="mdi:timer-sand",
            )]
            data.alert_summary = "Correction en cours"
            data.has_active_alert = True
            data.action_summary = (summary or "Correction en cours") + " · " + data.action_summary

        ctx = _water_balance_context(self)
        data.detail["water_balance_v2"] = {
            "ph_state": ctx["ph_state"],
            "ph_optimal_range": [PH_OPTIMAL_MIN, PH_OPTIMAL_MAX],
            "ph_operational_range": [PH_OPERATIONAL_MIN, PH_OPERATIONAL_MAX],
            "ta_target_range": [ctx["ta_target_low"], ctx["ta_target_high"]],
            "ta_general_range": [TA_GENERAL_LOW, TA_GENERAL_HIGH],
            "calcium_optimal_range": [CALCIUM_OPTIMAL_MIN, CALCIUM_OPTIMAL_MAX],
            "calcium_basis": ctx["calcium_basis"],
            "lsi_balanced_range": [LSI_BALANCED_MIN, LSI_BALANCED_MAX],
            "surface": ctx["surface"],
            "correction_locked": until is not None,
        }
        return data

    CoordinatorClass.async_load_products = async_load_products_v2
    CoordinatorClass.async_confirm_product_added = async_confirm_product_added_v2
    CoordinatorClass._build_recommendations = build_recommendations_v2
    CoordinatorClass._build_treatment_recommendations = build_treatment_recommendations_v2
    CoordinatorClass._chemistry_status = chemistry_status_v2
    CoordinatorClass._lsi = lsi_v2
    CoordinatorClass._calculate = calculate_v2
    CoordinatorClass._recommendation_engine_v2_installed = True
