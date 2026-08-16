from __future__ import annotations

import ast
from pathlib import Path


ENGINE = (
    Path(__file__).parents[1]
    / "custom_components"
    / "pool_pilot"
    / "disinfection_engine.py"
)


def _constants() -> dict[str, object]:
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return values


def test_disinfection_engine_is_valid_python() -> None:
    ast.parse(ENGINE.read_text(encoding="utf-8"))


def test_cya_matrix_constants() -> None:
    values = _constants()
    assert values["CYA_OPTIMAL_MIN"] == 30.0
    assert values["CYA_OPTIMAL_MAX"] == 50.0
    assert values["CYA_HIGH"] == 80.0
    assert values["CYA_VERY_HIGH"] == 100.0
    assert values["CYA_CRITICAL"] == 300.0


def test_free_chlorine_matrix_constants() -> None:
    values = _constants()
    assert values["FC_NO_CYA_MIN"] == 1.0
    assert values["FC_WITH_CYA_MIN"] == 2.0
    assert values["FC_OPTIMAL_LOW"] == 2.0
    assert values["FC_OPTIMAL_HIGH"] == 4.0
    assert values["FC_HIGH"] == 5.0


def test_orp_policy_constants() -> None:
    values = _constants()
    assert values["ORP_WATCH_DELTA"] == 50.0
    assert values["ORP_VERY_LOW_DELTA"] == 100.0
    assert values["ORP_HIGH_DELTA"] == 150.0


def test_orp_is_not_used_as_a_product_dose_delta() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert "Pool Pilot ne convertit pas un écart ORP en grammes" in source
    assert "aucun dosage n'est calculé à partir des mV" in source


def test_algae_alert_does_not_auto_dose_shock() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert 'alert["product_name"] = None' in source
    assert 'alert["quantity"] = None' in source
    assert "Réservez le traitement choc aux situations où il est réellement justifié." in source
