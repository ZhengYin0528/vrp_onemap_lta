from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def build_benchmark_summary(
    greedy: Dict[str, Any],
    ga_only: Dict[str, Any],
    ga_bo: Dict[str, Any],
    exact_small: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    summary = {
        "main_case": {
            "greedy": {
                "objective": greedy["objective"],
                "total_distance_km": sum(greedy["route_distance_km"]),
                "total_time_min": sum(greedy["route_time_min"]),
            },
            "ga_only": {
                "objective": ga_only["objective"],
                "total_distance_km": sum(ga_only["route_distance_km"]),
                "total_time_min": sum(ga_only["route_time_min"]),
            },
            "ga_bo": {
                "objective": ga_bo["objective"],
                "total_distance_km": sum(ga_bo["route_distance_km"]),
                "total_time_min": sum(ga_bo["route_time_min"]),
            },
        }
    }

    if exact_small is not None:
        summary["small_case_validation"] = exact_small

    g = greedy["objective"]
    ga = ga_only["objective"]
    gabo = ga_bo["objective"]

    summary["improvement_percent"] = {
        "ga_only_vs_greedy": 100.0 * (g - ga) / g if g else 0.0,
        "ga_bo_vs_greedy": 100.0 * (g - gabo) / g if g else 0.0,
        "ga_bo_vs_ga_only": 100.0 * (ga - gabo) / ga if ga else 0.0,
    }

    return summary


def save_benchmark_summary(summary: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)