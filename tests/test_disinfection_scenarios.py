from __future__ import annotations

import ast
from pathlib import Path

import pytest


ENGINE = (
    Path(__file__).parents[1]
    / "custom_components"
    / "pool_pilot"
    / "disinfection_engine.py"
)

PURE_NAMES = {
    "CYA_OPTIMAL_MIN",
    "CYA_OPTIMAL_MAX",
    "CYA_HIGH",
    "CYA_VERY_HIGH",
    "CYA_CRITICAL",
    "FC_NO_CYA_MIN",
    "FC_WITH_CYA_MIN",
    "FC_OPTIMAL_LOW",
    "FC_OPTIMAL_HIGH",
    "FC_HIGH",
    "ORP_WATCH_DELTA",
    "ORP_VERY_LOW_DELTA",
    "ORP_HIGH_DELTA",
    "cya_state",
    "fc_minimum",
    "fc_state",
    "orp_state",
}


def _load_pure_policy() -> dict[str, object]:
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id in PURE_NAMES for target in node.targets):
                selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in PURE_NAMES:
            selected.append(node)
    module = ast.Module(body=selected, type_ignores=[])
    namespace: dict[str, object] = {}
    exec(compile(ast.fix_missing_locations(module), str(ENGINE), "exec"), namespace)
    return namespace


@pytest.fixture(scope="module")
def policy() -> dict[str, object]:
    return _load_pure_policy()


@pytest.mark.parametrize(
    ("cya", "expected"),
    [
        (None, "unknown"),
        (0, "none"),
        (1, "low"),
        (29.9, "low"),
        (30, "optimal"),
        (50, "optimal"),
        (50.1, "watch_high"),
        (80, "watch_high"),
        (80.1, "high"),
        (100, "high"),
        (100.1, "very_high"),
        (299.9, "very_high"),
        (300, "critical"),
    ],
)
def test_cya_scenarios(policy: dict[str, object], cya: float | None, expected: str) -> None:
    assert policy["cya_state"](cya) == expected


@pytest.mark.parametrize(
    ("fc", "cya", "expected"),
    [
        (0.8, 0, "low"),
        (1.0, 0, "watch_low"),
        (1.5, 0, "watch_low"),
        (2.0, 0, "optimal"),
        (4.0, 0, "optimal"),
        (4.5, 0, "watch_high"),
        (5.0, 0, "watch_high"),
        (5.1, 0, "high"),
        (1.9, 40, "low"),
        (2.0, 40, "optimal"),
        (3.0, 40, "optimal"),
        (5.5, 40, "high"),
    ],
)
def test_free_chlorine_scenarios(policy: dict[str, object], fc: float, cya: float, expected: str) -> None:
    assert policy["fc_state"](fc, cya) == expected


@pytest.mark.parametrize(
    ("orp", "target", "expected"),
    [
        (700, 700, "ok"),
        (699, 700, "watch_low"),
        (651, 700, "watch_low"),
        (650, 700, "low"),
        (601, 700, "low"),
        (600, 700, "very_low"),
        (850, 700, "ok"),
        (851, 700, "high"),
    ],
)
def test_orp_boundary_scenarios(policy: dict[str, object], orp: float, target: float, expected: str) -> None:
    assert policy["orp_state"](orp, target) == expected


def test_cross_measurement_matrix(policy: dict[str, object]) -> None:
    fc_state = policy["fc_state"]
    orp_state = policy["orp_state"]

    scenarios = {
        "balanced": ("optimal", "ok"),
        "confirmed_deficit": ("low", "low"),
        "fc_ok_orp_low": ("optimal", "low"),
        "fc_high_orp_low": ("high", "low"),
        "fc_low_orp_ok": ("low", "ok"),
        "both_high": ("high", "high"),
    }

    actual = {
        "balanced": (fc_state(3.0, 40), orp_state(700, 700)),
        "confirmed_deficit": (fc_state(1.2, 40), orp_state(640, 700)),
        "fc_ok_orp_low": (fc_state(3.0, 40), orp_state(640, 700)),
        "fc_high_orp_low": (fc_state(6.0, 40), orp_state(640, 700)),
        "fc_low_orp_ok": (fc_state(1.2, 40), orp_state(710, 700)),
        "both_high": (fc_state(6.0, 40), orp_state(851, 700)),
    }

    assert actual == scenarios


def test_high_cya_blocks_automatic_chlorine_dose_in_source() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert "if cya is not None and cya > CYA_VERY_HIGH:" in source
    assert "return None" in source
    assert "N'ajoutez plus de stabilisant ou de chlore stabilisé" in source


def test_low_orp_with_measured_fc_does_not_become_mv_based_dose() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert "Pool Pilot ne convertit pas un écart ORP en grammes" in source
    assert "aucun dosage n'est calculé à partir des mV" in source


def test_salt_strategy_prefers_electrolyzer() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert 'action="electrolyzer_boost"' in source
    assert 'action="electrolyzer_increase"' in source
    assert 'action="electrolyzer_reduce"' in source


def test_algae_risk_does_not_emit_automatic_shock_quantity() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert 'alert["product_name"] = None' in source
    assert 'alert["quantity"] = None' in source
    assert "Réservez le traitement choc aux situations où il est réellement justifié." in source
