"""Disinfection recommendation engine v2 for Pool Pilot.

Adds CYA/free-chlorine/ORP decision rules on top of the water-balance v2
engine. The key safety principles are:
- water balance is resolved before disinfection;
- ORP is never converted directly into a chemical quantity;
- CYA influences diagnosis and product selection;
- manufacturer product effect is required before a calculated dose is emitted;
- salt pools prioritize electrolyzer production/Boost;
- algae risk alone never triggers an automatic shock dose.
"""
from __future__ import annotations

from datetime import timedelta
import json
from typing import Any

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CYA_ENTITY,
    CONF_FC_ENTITY,
    CONF_ORP_ENTITY,
    CONF_PH_ENTITY,
    CONF_TA_ENTITY,
    CONF_CH_ENTITY,
    CONF_TARGET_FC,
    CONF_TARGET_ORP,
    CONF_VOLUME_M3,
    DEFAULT_TARGET_FC,
    DEFAULT_TARGET_ORP,
    DOMAIN,
    MEASUREMENT_MODE_ORP,
    POOL_TYPE_ACTIVE_OXYGEN,
    POOL_TYPE_BROMINE,
    POOL_TYPE_CHLORINE,
    POOL_TYPE_SALT,
)

PH_OPERATIONAL_MIN = 7.00
PH_OPERATIONAL_MAX = 7.80
TA_GENERAL_LOW = 60.0
CALCIUM_VERY_LOW = 150.0
LSI_BALANCED_MIN = -0.20

CYA_OPTIMAL_MIN = 30.0
CYA_OPTIMAL_MAX = 50.0
CYA_HIGH = 80.0
CYA_VERY_HIGH = 100.0
CYA_CRITICAL = 300.0

FC_NO_CYA_MIN = 1.0
FC_WITH_CYA_MIN = 2.0
FC_OPTIMAL_LOW = 2.0
FC_OPTIMAL_HIGH = 4.0
FC_HIGH = 5.0

ORP_WATCH_DELTA = 50.0
ORP_VERY_LOW_DELTA = 100.0
ORP_HIGH_DELTA = 150.0

DISINFECTION_CATEGORIES = {
    "chlorine",
    "chlorine_slow",
    "chlorine_shock",
    "chlorine_liquid",
    "bromine",
    "active_oxygen",
}
STRUCTURAL_CATEGORIES = {
    "ph_minus",
    "ph_plus",
    "alkalinity",
    "alkalinity_minus",
    "hardness_plus",
    "hardness_minus",
}
STRUCTURAL_ACTION_PREFIXES = (
    "water_balance_",
    "verify_measurement",
    "correction_wait",
)

CORRECTION_STORAGE_VERSION = 1
CORRECTION_STORAGE_PREFIX = f"{DOMAIN}_recommendation_v2"


def _notes(product: Any) -> dict[str, Any]:
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


def _is_stabilized(product: Any) -> bool:
    notes = _notes(product)
    value = notes.get("stabilized")
    if isinstance(value, str):
        value = value.strip().lower() in {"1", "true", "yes", "oui", "on"}
    return bool(value) or str(getattr(product, "category", "")) == "chlorine_slow"


def _manufacturer_quantity(coordinator: Any, product: Any, desired_delta: float) -> float | None:
    """Calculate a dose only when the product declares a usable effect_delta."""
    try:
        effect = abs(float(product.effect_delta)) if product.effect_delta is not None else 0.0
        if effect <= 0 or desired_delta <= 0:
            return None
        volume = float(coordinator.config_entry.data.get(CONF_VOLUME_M3) or 0)
        basis = float(product.volume_basis_m3 or 0)
        base_qty = float(product.dosage_quantity or 0)
        if volume <= 0 or basis <= 0 or base_qty <= 0:
            return None
        quantity = base_qty * (volume / basis) * (abs(float(desired_delta)) / effect)
        max_single = _notes(product).get("max_single_dose_amount")
        if max_single not in (None, ""):
            try:
                quantity = min(quantity, max(0.0, float(max_single)))
            except (TypeError, ValueError):
                pass
        return round(max(0.0, quantity), 2)
    except Exception:
        return None


def _stock_after(product: Any, quantity: float) -> float | None:
    stock = getattr(product, "stock_quantity", None)
    if stock is None or getattr(product, "stock_unit", None) != getattr(product, "dosage_unit", None):
        return None
    return float(stock) - float(quantity)


def cya_state(cya: float | None) -> str:
    if cya is None:
        return "unknown"
    if cya <= 0:
        return "none"
    if cya < CYA_OPTIMAL_MIN:
        return "low"
    if cya <= CYA_OPTIMAL_MAX:
        return "optimal"
    if cya <= CYA_HIGH:
        return "watch_high"
    if cya <= CYA_VERY_HIGH:
        return "high"
    if cya < CYA_CRITICAL:
        return "very_high"
    return "critical"


def fc_minimum(cya: float | None) -> float:
    return FC_WITH_CYA_MIN if cya is not None and cya > 0 else FC_NO_CYA_MIN


def fc_state(fc: float | None, cya: float | None) -> str:
    if fc is None:
        return "unknown"
    minimum = fc_minimum(cya)
    if fc < minimum:
        return "low"
    if fc < FC_OPTIMAL_LOW:
        return "watch_low"
    if fc <= FC_OPTIMAL_HIGH:
        return "optimal"
    if fc <= FC_HIGH:
        return "watch_high"
    return "high"


def orp_state(orp: float | None, target: float) -> str:
    if orp is None:
        return "unknown"
    delta = float(orp) - float(target)
    if delta <= -ORP_VERY_LOW_DELTA:
        return "very_low"
    if delta <= -ORP_WATCH_DELTA:
        return "low"
    if delta < 0:
        return "watch_low"
    if delta > ORP_HIGH_DELTA:
        return "high"
    return "ok"


def _recent_strip_value(coordinator: Any, key: str, max_age_hours: float = 72.0) -> float | None:
    value = coordinator.strip_test.get(key)
    if value is None:
        return None
    raw_updated = coordinator.strip_test.get("updated_at")
    if raw_updated:
        try:
            updated = dt_util.parse_datetime(str(raw_updated))
            if updated is not None:
                age = dt_util.now() - dt_util.as_local(updated)
                if age > timedelta(hours=max_age_hours):
                    return None
        except Exception:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _measured_fc(coordinator: Any) -> float | None:
    entity = coordinator.config_entry.data.get(CONF_FC_ENTITY)
    live = coordinator._float(entity)
    if live is not None:
        return live
    return _recent_strip_value(coordinator, "free_chlorine")


def _cya(coordinator: Any) -> float | None:
    d = coordinator.config_entry.data
    return coordinator._strip_or_entity_float("cya", d.get(CONF_CYA_ENTITY), prefer_strip=True)


def _water_balance_blocks(coordinator: Any, ph: float | None) -> bool:
    d = coordinator.config_entry.data
    ta = coordinator._strip_or_entity_float("alkalinity", d.get(CONF_TA_ENTITY), prefer_strip=True)
    calcium = coordinator._strip_or_entity_float("calcium", d.get(CONF_CH_ENTITY), prefer_strip=True)
    temp = coordinator._temp_c(d.get("temp_entity"))
    salt = coordinator._float(d.get("salt_entity"))
    lsi, *_ = coordinator._lsi(ph, temp, ta, calcium, salt)
    if ph is not None and (ph < PH_OPERATIONAL_MIN or ph > PH_OPERATIONAL_MAX):
        return True
    if ta is not None and ta < TA_GENERAL_LOW:
        return True
    if calcium is not None and calcium < CALCIUM_VERY_LOW and lsi is not None and lsi < LSI_BALANCED_MIN:
        return True
    return False


def _available_products(coordinator: Any, categories: tuple[str, ...]) -> list[Any]:
    result = []
    for p in coordinator.products.values():
        if str(getattr(p, "category", "")) not in categories:
            continue
        stock = getattr(p, "stock_quantity", None)
        if stock is not None:
            try:
                if float(stock) <= 0:
                    continue
            except Exception:
                pass
        result.append(p)
    return result


def _select_chlorine_product(coordinator: Any, cya: float | None) -> Any | None:
    products = _available_products(
        coordinator,
        ("chlorine_liquid", "chlorine_slow", "chlorine_shock", "chlorine"),
    )
    if not products:
        return None
    if cya is not None and cya > CYA_HIGH:
        non_stabilized = [p for p in products if not _is_stabilized(p)]
        if non_stabilized:
            products = non_stabilized
    priority = {
        "chlorine_liquid": 0,
        "chlorine_slow": 1,
        "chlorine": 2,
        "chlorine_shock": 3,
    }
    return sorted(products, key=lambda p: priority.get(str(getattr(p, "category", "")), 9))[0]


def _select_primary_product(coordinator: Any, cya: float | None) -> Any | None:
    pool_type = coordinator._pool_type()
    if pool_type == POOL_TYPE_BROMINE:
        products = _available_products(coordinator, ("bromine",))
        return products[0] if products else None
    if pool_type == POOL_TYPE_ACTIVE_OXYGEN:
        products = _available_products(coordinator, ("active_oxygen",))
        return products[0] if products else None
    if pool_type == POOL_TYPE_CHLORINE:
        return _select_chlorine_product(coordinator, cya)
    return None


def _configured_fc_target(coordinator: Any, cya: float | None) -> float:
    configured = float(coordinator.option(CONF_TARGET_FC, DEFAULT_TARGET_FC))
    lower = fc_minimum(cya)
    return max(lower, min(FC_OPTIMAL_HIGH, configured))


def _disinfection_product_recommendation(
    coordinator: Any,
    ProductRecommendation: Any,
    fc: float | None,
    cya: float | None,
) -> Any | None:
    if fc is None:
        return None
    if cya is not None and cya > CYA_VERY_HIGH:
        return None
    pool_type = coordinator._pool_type()
    if pool_type == POOL_TYPE_SALT:
        return None
    if pool_type not in (POOL_TYPE_CHLORINE,):
        return None
    if fc_state(fc, cya) != "low":
        return None
    product = _select_primary_product(coordinator, cya)
    if product is None:
        return None
    target = _configured_fc_target(coordinator, cya)
    qty = _manufacturer_quantity(coordinator, product, max(0.0, target - fc))
    if qty is None or qty <= 0:
        return None
    reason = f"Chlore libre {fc:.2f} ppm, minimum opérationnel {fc_minimum(cya):.1f} ppm"
    if cya is not None:
        reason += f", CYA {cya:.0f} ppm"
    if cya is not None and cya > CYA_HIGH and not _is_stabilized(product):
        reason += " : produit non stabilisé privilégié."
    else:
        reason += "."
    return ProductRecommendation(
        product.id,
        product.name,
        product.category,
        qty,
        product.dosage_unit,
        reason,
        aftercare=(
            "Dose calculée uniquement à partir de l'effet fabricant renseigné. "
            "Laissez circuler puis recontrôlez le chlore avant une nouvelle correction."
        ),
        stock_after=_stock_after(product, qty),
        stock_unit=product.stock_unit,
    )


def _cya_advisory(coordinator: Any, TreatmentRecommendation: Any, cya: float | None) -> Any | None:
    treatment = coordinator._pool_type()
    if treatment not in (POOL_TYPE_CHLORINE, POOL_TYPE_SALT):
        return None
    state = cya_state(cya)
    if state == "critical":
        return TreatmentRecommendation(
            action="cya_critical",
            title="Stabilisant extrêmement élevé",
            message=(
                f"CYA {cya:.0f} ppm. N'ajoutez plus de stabilisant ou de chlore stabilisé. "
                "Une réduction du CYA par renouvellement/dilution de l'eau est prioritaire."
            ),
            treatment=treatment,
            icon="mdi:water-alert",
        )
    if state == "very_high":
        return TreatmentRecommendation(
            action="cya_reduce",
            title="Stabilisant trop élevé",
            message=(
                f"CYA {cya:.0f} ppm. Évitez les produits chlorés stabilisés et prévoyez "
                "une réduction progressive du CYA par renouvellement d'eau."
            ),
            treatment=treatment,
            icon="mdi:water-percent-alert",
        )
    if state == "high":
        return TreatmentRecommendation(
            action="cya_high",
            title="Stabilisant élevé",
            message=(
                f"CYA {cya:.0f} ppm. N'ajoutez pas de stabilisant et privilégiez un chlore "
                "non stabilisé lorsqu'une correction de désinfection est nécessaire."
            ),
            treatment=treatment,
            icon="mdi:water-percent",
        )
    if state == "watch_high":
        return TreatmentRecommendation(
            action="cya_watch",
            title="Stabilisant à surveiller",
            message=f"CYA {cya:.0f} ppm. Évitez d'augmenter inutilement le stabilisant.",
            treatment=treatment,
            icon="mdi:eye-outline",
        )
    if state == "low":
        return TreatmentRecommendation(
            action="cya_low_watch",
            title="Stabilisant faible",
            message=(
                f"CYA {cya:.0f} ppm. Valeur basse : en bassin extérieur, la protection du chlore "
                "contre les UV peut être limitée. Aucun ajout automatique n'est proposé."
            ),
            treatment=treatment,
            icon="mdi:weather-sunny-alert",
        )
    return None


def _salt_low_advisory(coordinator: Any, TreatmentRecommendation: Any, severe: bool) -> Any:
    boost_entity = coordinator.config_entry.data.get("electrolyzer_boost_entity")
    output_entity = coordinator.config_entry.data.get("electrolyzer_output_entity")
    if severe and boost_entity:
        return TreatmentRecommendation(
            action="electrolyzer_boost",
            title="Désinfection à renforcer",
            message="Activez temporairement le mode Boost de l'électrolyseur puis contrôlez de nouveau la désinfection.",
            treatment=POOL_TYPE_SALT,
            entity_id=boost_entity,
            service="turn_on",
            icon="mdi:lightning-bolt",
        )
    if output_entity:
        return TreatmentRecommendation(
            action="electrolyzer_increase",
            title="Production à augmenter",
            message=(
                "Augmentez temporairement la production de l'électrolyseur. "
                "Si la désinfection reste faible, contrôlez sel, durée de filtration, cellule, pH et CYA."
            ),
            treatment=POOL_TYPE_SALT,
            entity_id=output_entity,
            icon="mdi:chart-line",
        )
    return TreatmentRecommendation(
        action="electrolyzer_increase",
        title="Production à augmenter",
        message=(
            "Renforcez temporairement la production de l'électrolyseur ou utilisez son mode Boost. "
            "Si le problème persiste, contrôlez sel, filtration, cellule, pH et CYA."
        ),
        treatment=POOL_TYPE_SALT,
        icon="mdi:lightning-bolt",
    )


def _salt_high_advisory(coordinator: Any, TreatmentRecommendation: Any) -> Any:
    output_entity = coordinator.config_entry.data.get("electrolyzer_output_entity")
    return TreatmentRecommendation(
        action="electrolyzer_reduce",
        title="Production à réduire",
        message="Réduisez temporairement la production de l'électrolyseur et recontrôlez la désinfection.",
        treatment=POOL_TYPE_SALT,
        entity_id=output_entity,
        icon="mdi:chart-line-variant",
    )


def _orp_fc_advisory(
    coordinator: Any,
    TreatmentRecommendation: Any,
    orp: float | None,
    measured_fc: float | None,
    cya: float | None,
) -> Any | None:
    treatment = coordinator._pool_type()
    target_orp = float(coordinator.option(CONF_TARGET_ORP, DEFAULT_TARGET_ORP))
    ostate = orp_state(orp, target_orp)
    fstate = fc_state(measured_fc, cya)

    if orp is None:
        return None

    if treatment in (POOL_TYPE_BROMINE, POOL_TYPE_ACTIVE_OXYGEN):
        if ostate in ("low", "very_low"):
            label = "brome" if treatment == POOL_TYPE_BROMINE else "oxygène actif"
            return TreatmentRecommendation(
                action="disinfection_reinforce_manual",
                title="Désinfection à renforcer",
                message=(
                    f"ORP {orp:.0f} mV pour une cible de {target_orp:.0f} mV. "
                    f"Renforcez le traitement au {label} selon la dose corrective fabricant; "
                    "Pool Pilot ne convertit pas un écart ORP en grammes."
                ),
                treatment=treatment,
                icon="mdi:flask-outline",
            )
        if ostate == "high":
            return TreatmentRecommendation(
                action="disinfection_high",
                title="Pouvoir oxydant élevé",
                message=(
                    f"ORP {orp:.0f} mV, nettement au-dessus de la cible {target_orp:.0f} mV. "
                    "N'ajoutez pas de désinfectant et contrôlez de nouveau la mesure."
                ),
                treatment=treatment,
                icon="mdi:chart-bell-curve",
            )
        return None

    if measured_fc is not None:
        if fstate == "low" and ostate in ("low", "very_low"):
            if treatment == POOL_TYPE_SALT:
                return _salt_low_advisory(coordinator, TreatmentRecommendation, severe=(ostate == "very_low"))
            return TreatmentRecommendation(
                action="disinfection_low_confirmed",
                title="Désinfection insuffisante confirmée",
                message=(
                    f"Chlore libre {measured_fc:.2f} ppm et ORP {orp:.0f} mV sont tous deux bas. "
                    "Une correction du traitement est justifiée."
                ),
                treatment=treatment,
                icon="mdi:water-alert",
            )
        if fstate in ("optimal", "watch_high", "high") and ostate in ("low", "very_low"):
            return TreatmentRecommendation(
                action="orp_diagnostic",
                title="ORP faible malgré un chlore présent",
                message=(
                    f"ORP {orp:.0f} mV mais chlore libre {measured_fc:.2f} ppm. "
                    "N'ajoutez pas automatiquement de chlore : vérifiez pH, CYA, état de la sonde "
                    "et équilibre de l'eau."
                ),
                treatment=treatment,
                icon="mdi:chart-bell-curve",
            )
        if fstate == "low" and ostate in ("ok", "watch_low"):
            return TreatmentRecommendation(
                action="verify_disinfection_measurement",
                title="Mesures de désinfection discordantes",
                message=(
                    f"Chlore libre {measured_fc:.2f} ppm bas mais ORP {orp:.0f} mV encore correct. "
                    "Confirmez le chlore avant un traitement important."
                ),
                treatment=treatment,
                icon="mdi:test-tube",
            )
        if fstate == "high" and ostate == "high":
            if treatment == POOL_TYPE_SALT:
                return _salt_high_advisory(coordinator, TreatmentRecommendation)
            return TreatmentRecommendation(
                action="disinfection_high",
                title="Désinfection élevée",
                message=(
                    f"Chlore libre {measured_fc:.2f} ppm et ORP {orp:.0f} mV sont élevés. "
                    "N'ajoutez plus de désinfectant et contrôlez de nouveau après circulation."
                ),
                treatment=treatment,
                icon="mdi:water-minus",
            )

    if ostate == "very_low":
        if treatment == POOL_TYPE_SALT:
            return _salt_low_advisory(coordinator, TreatmentRecommendation, severe=True)
        return TreatmentRecommendation(
            action="orp_very_low",
            title="ORP très faible",
            message=(
                f"ORP {orp:.0f} mV, plus de {ORP_VERY_LOW_DELTA:.0f} mV sous la cible. "
                "Confirmez la désinfection avec une mesure de chlore libre si possible avant un dosage chimique."
            ),
            treatment=treatment,
            icon="mdi:chart-bell-curve",
        )
    if ostate == "low":
        if treatment == POOL_TYPE_SALT:
            return _salt_low_advisory(coordinator, TreatmentRecommendation, severe=False)
        return TreatmentRecommendation(
            action="orp_low",
            title="ORP faible",
            message=(
                f"ORP {orp:.0f} mV sous la cible {target_orp:.0f} mV. "
                "Surveillez et confirmez avec le chlore libre; aucun dosage n'est calculé à partir des mV."
            ),
            treatment=treatment,
            icon="mdi:chart-bell-curve",
        )
    if ostate == "watch_low":
        return TreatmentRecommendation(
            action="orp_watch",
            title="ORP légèrement sous la cible",
            message=f"ORP {orp:.0f} mV pour une cible de {target_orp:.0f} mV : surveillance sans correction immédiate.",
            treatment=treatment,
            icon="mdi:eye-outline",
        )
    if ostate == "high":
        if treatment == POOL_TYPE_SALT:
            return _salt_high_advisory(coordinator, TreatmentRecommendation)
        return TreatmentRecommendation(
            action="orp_high",
            title="ORP élevé",
            message=f"ORP {orp:.0f} mV, nettement au-dessus de la cible. N'ajoutez pas de désinfectant.",
            treatment=treatment,
            icon="mdi:chart-bell-curve",
        )
    return None


def _missing_dose_advisory(
    coordinator: Any,
    TreatmentRecommendation: Any,
    fc: float | None,
    cya: float | None,
) -> Any | None:
    if coordinator._pool_type() != POOL_TYPE_CHLORINE or fc is None or fc_state(fc, cya) != "low":
        return None
    product = _select_primary_product(coordinator, cya)
    if product is None:
        return TreatmentRecommendation(
            action="disinfection_product_missing",
            title="Désinfection à renforcer",
            message="Le chlore libre est insuffisant, mais aucun produit chloré compatible n'est renseigné dans Pool House.",
            treatment=POOL_TYPE_CHLORINE,
            icon="mdi:bottle-tonic-outline",
        )
    target = _configured_fc_target(coordinator, cya)
    if _manufacturer_quantity(coordinator, product, max(0.0, target - fc)) is None:
        return TreatmentRecommendation(
            action="disinfection_dose_missing",
            title="Désinfection à renforcer",
            message=(
                f"Le produit {product.name} est compatible, mais son effet fabricant n'est pas renseigné. "
                "Pool Pilot ne calcule donc pas de quantité."
            ),
            treatment=POOL_TYPE_CHLORINE,
            icon="mdi:bottle-tonic-outline",
        )
    return None


def install_disinfection_engine_v2(CoordinatorClass: Any) -> None:
    """Install CYA/chlorine/ORP/salt v2 rules after water-balance v2."""
    if getattr(CoordinatorClass, "_disinfection_engine_v2_installed", False):
        return

    from .coordinator import ProductRecommendation, TreatmentRecommendation

    water_build_recommendations = CoordinatorClass._build_recommendations
    water_build_treatment_recommendations = CoordinatorClass._build_treatment_recommendations
    water_chemistry_status = CoordinatorClass._chemistry_status
    water_confirm_product = CoordinatorClass.async_confirm_product_added
    original_build_pool_alerts = CoordinatorClass._build_pool_alerts
    original_scenario_steps = CoordinatorClass._scenario_steps

    def build_recommendations_v2(
        self: Any,
        ph: float | None,
        fc: float | None,
        orp: float | None,
        algae_score: float | None = None,
    ) -> list[Any]:
        water_recs = water_build_recommendations(self, ph, fc, orp, algae_score)
        structural = [
            r for r in water_recs
            if str(getattr(r, "category", "")) in STRUCTURAL_CATEGORIES
        ]
        if structural:
            return structural[:1]
        if getattr(self, "_recommendation_v2_correction_until", None) is not None:
            try:
                if dt_util.now() < self._recommendation_v2_correction_until:
                    return []
            except Exception:
                pass
        if _water_balance_blocks(self, ph):
            return []

        cya = _cya(self)
        measured_fc = _measured_fc(self)
        mode = self._disinfection_mode()
        dose_fc = fc if mode != MEASUREMENT_MODE_ORP else measured_fc

        rec = _disinfection_product_recommendation(
            self, ProductRecommendation, dose_fc, cya
        )
        return [rec] if rec is not None else []

    def build_treatment_recommendations_v2(
        self: Any,
        fc: float | None,
        orp: float | None,
    ) -> list[Any]:
        water_recs = water_build_treatment_recommendations(self, fc, orp)
        structural = [
            r for r in water_recs
            if str(getattr(r, "action", "")).startswith(STRUCTURAL_ACTION_PREFIXES)
        ]
        if structural:
            return structural[:1]

        ph = self._strip_or_entity_float(
            "ph", self.config_entry.data.get(CONF_PH_ENTITY), prefer_strip=False
        )
        if _water_balance_blocks(self, ph):
            return water_recs[:1]

        cya = _cya(self)
        cya_advice = _cya_advisory(self, TreatmentRecommendation, cya)
        if cya_advice is not None and cya_state(cya) in {"very_high", "critical"}:
            return [cya_advice]

        measured_fc = _measured_fc(self)
        mode = self._disinfection_mode()

        if mode == MEASUREMENT_MODE_ORP:
            advice = _orp_fc_advisory(
                self, TreatmentRecommendation, orp, measured_fc, cya
            )
            if advice is not None:
                return [advice]
        else:
            fstate = fc_state(fc, cya)
            if self._pool_type() == POOL_TYPE_SALT:
                if fstate == "low":
                    return [_salt_low_advisory(self, TreatmentRecommendation, severe=fc is not None and fc < fc_minimum(cya) * 0.5)]
                if fstate == "high":
                    return [_salt_high_advisory(self, TreatmentRecommendation)]
            elif self._pool_type() == POOL_TYPE_CHLORINE:
                missing = _missing_dose_advisory(self, TreatmentRecommendation, fc, cya)
                if missing is not None:
                    return [missing]
                if fstate == "high":
                    return [TreatmentRecommendation(
                        action="chlorine_high",
                        title="Chlore libre élevé",
                        message=f"Chlore libre {fc:.2f} ppm. N'ajoutez plus de chlore et recontrôlez après circulation.",
                        treatment=POOL_TYPE_CHLORINE,
                        icon="mdi:water-minus",
                    )]

        if cya_advice is not None:
            return [cya_advice]
        return []

    def chemistry_status_v2(
        self: Any,
        ph: float | None,
        orp: float | None,
        fc: float | None,
    ) -> tuple[str, list[str]]:
        status, alerts = water_chemistry_status(self, ph, orp, fc)
        alerts = [
            a for a in alerts
            if not (
                a.startswith("RedOx bas:")
                or a.startswith("RedOx élevé:")
                or a.startswith("Chlore libre bas:")
            )
        ]
        if ph is None and orp is None and fc is None:
            return status, alerts

        cya = _cya(self)
        cstate = cya_state(cya)
        mode = self._disinfection_mode()
        measured_fc = _measured_fc(self)

        if self._pool_type() in (POOL_TYPE_CHLORINE, POOL_TYPE_SALT) and cstate in {"high", "very_high", "critical"}:
            alerts.append(f"Stabilisant élevé: {cya:.0f} ppm")
            status = "warning"

        if mode == MEASUREMENT_MODE_ORP:
            target = float(self.option(CONF_TARGET_ORP, DEFAULT_TARGET_ORP))
            ostate = orp_state(orp, target)
            if ostate in {"low", "very_low"}:
                if measured_fc is not None and fc_state(measured_fc, cya) not in {"low", "watch_low"}:
                    alerts.append("ORP faible malgré un chlore libre présent: diagnostic recommandé")
                else:
                    alerts.append(f"RedOx bas: {orp:.0f} mV, cible {target:.0f} mV")
                status = "warning"
            elif ostate == "high":
                alerts.append(f"RedOx élevé: {orp:.0f} mV, cible {target:.0f} mV")
                status = "warning"
        elif fc is not None:
            fstate = fc_state(fc, cya)
            if fstate == "low":
                alerts.append(
                    f"Chlore libre bas: {fc:.2f} ppm, minimum {fc_minimum(cya):.1f} ppm"
                )
                status = "warning"
            elif fstate == "high":
                alerts.append(f"Chlore libre élevé: {fc:.2f} ppm")
                status = "warning"
        return status, alerts

    def build_pool_alerts_v2(
        self: Any,
        water_temp: float | None,
        ph: float | None,
        orp: float | None,
        fc: float | None,
        weather_factor: float,
    ) -> list[dict[str, Any]]:
        alerts = original_build_pool_alerts(
            self, water_temp, ph, orp, fc, weather_factor
        )
        for alert in alerts:
            if alert.get("id") != "green_algae_risk":
                continue
            alert["product_name"] = None
            alert["quantity"] = None
            alert["unit"] = None
            alert["action_type"] = "algae_diagnostic"
            alert["steps"] = [
                "Contrôlez d'abord le pH et l'équilibre de l'eau.",
                "Vérifiez la désinfection avec la mesure disponible et recherchez la cause du risque.",
                "Brossez les parois et le fond si nécessaire.",
                "Renforcez la filtration.",
                "Ne réalisez un traitement choc que si l'état réel de l'eau et le produit utilisé le justifient.",
            ]
        return alerts

    def scenario_steps_v2(
        self: Any,
        alert_id: str,
        product_name: str | None = None,
        product_qty: float | None = None,
        product_unit: str | None = None,
    ) -> list[str]:
        if alert_id == "green_algae_risk":
            return [
                "Contrôlez d'abord le pH et l'équilibre de l'eau.",
                "Confirmez la désinfection et identifiez la cause du risque d'algues.",
                "Brossez les parois et le fond du bassin si nécessaire.",
                "Renforcez la filtration.",
                "Réservez le traitement choc aux situations où il est réellement justifié.",
            ]
        return original_scenario_steps(
            self, alert_id, product_name, product_qty, product_unit
        )

    async def confirm_product_v2(
        self: Any,
        product_id: str,
        quantity: float | None = None,
    ) -> None:
        product = self.products.get(product_id)
        await water_confirm_product(self, product_id, quantity)
        if product is None:
            return
        category = str(getattr(product, "category", "") or "")
        if category not in DISINFECTION_CATEGORIES:
            return

        hold_hours = 4
        until = dt_util.now() + timedelta(hours=hold_hours)
        self._recommendation_v2_correction_until = until
        self._recommendation_v2_correction_summary = (
            f"Correction de désinfection confirmée avec {product.name}. "
            "Attendez la circulation de l'eau et une nouvelle mesure avant une autre dose."
        )
        self._recommendation_v2_correction_category = category
        try:
            store = Store(
                self.hass,
                CORRECTION_STORAGE_VERSION,
                f"{CORRECTION_STORAGE_PREFIX}_{self.config_entry.entry_id}",
            )
            await store.async_save({
                "correction_until": until.isoformat(),
                "correction_summary": self._recommendation_v2_correction_summary,
                "correction_category": category,
            })
        except Exception:
            pass
        await self.async_request_refresh()

    CoordinatorClass._build_recommendations = build_recommendations_v2
    CoordinatorClass._build_treatment_recommendations = build_treatment_recommendations_v2
    CoordinatorClass._chemistry_status = chemistry_status_v2
    CoordinatorClass._build_pool_alerts = build_pool_alerts_v2
    CoordinatorClass._scenario_steps = scenario_steps_v2
    CoordinatorClass.async_confirm_product_added = confirm_product_v2
    CoordinatorClass._disinfection_engine_v2_installed = True
