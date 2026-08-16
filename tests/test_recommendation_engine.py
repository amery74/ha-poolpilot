from __future__ import annotations

import ast
from pathlib import Path


def test_recommendation_engine_is_valid_python() -> None:
    path = Path(__file__).parents[1] / "custom_components" / "pool_pilot" / "recommendation_engine.py"
    ast.parse(path.read_text(encoding="utf-8"))


def test_water_balance_constants_are_conservative() -> None:
    path = Path(__file__).parents[1] / "custom_components" / "pool_pilot" / "recommendation_engine.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    assert constants["PH_OPTIMAL_MIN"] == 7.20
    assert constants["PH_OPTIMAL_MAX"] == 7.60
    assert constants["PH_OPERATIONAL_MIN"] == 7.00
    assert constants["PH_OPERATIONAL_MAX"] == 7.80
    assert constants["TA_GENERAL_LOW"] == 60.0
    assert constants["TA_GENERAL_HIGH"] == 180.0
    assert constants["CALCIUM_OPTIMAL_MIN"] == 200.0
    assert constants["CALCIUM_OPTIMAL_MAX"] == 400.0
    assert constants["LSI_BALANCED_MIN"] == -0.20
    assert constants["LSI_BALANCED_MAX"] == 0.20
