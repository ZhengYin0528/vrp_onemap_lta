from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from .onemap_client import OneMapClient

Coord = Tuple[float, float]


def build_nodes(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = [case["depot"], case["incinerator"]]
    nodes.extend(case["bins"])
    return nodes

def build_route_matrices(
    nodes: List[Dict[str, Any]],
    onemap_client: OneMapClient,
    use_live_api: bool = False,
    cache_dir: str | Path = ".cache",
) -> Dict[str, Any]:
    n = len(nodes)
    time_minutes = np.zeros((n, n), dtype=float)
    distance_km = np.zeros((n, n), dtype=float)
    geometry: Dict[str, Dict[str, Any]] = {}

    for i in range(n):
        for j in range(n):
            if i == j:
                continue

            start = (nodes[i]["lat"], nodes[i]["lon"])
            end = (nodes[j]["lat"], nodes[j]["lon"])

            route_json = onemap_client.route_cached(start, end, use_live_api=use_live_api)
            tmin = onemap_client.parse_time_minutes(route_json, fallback_start=start, fallback_end=end)
            dist = onemap_client.parse_distance_km(route_json, fallback_start=start, fallback_end=end)
            coords, is_fallback = onemap_client.parse_route_geometry(route_json, start=start, end=end)

            time_minutes[i, j] = tmin
            distance_km[i, j] = dist
            geometry[f"{i}->{j}"] = {
                "coords": coords,
                "is_fallback": is_fallback,
            }

    return {
        "time_minutes": time_minutes,
        "distance_km": distance_km,
        "geometry": geometry,
    }

def _speed_penalty_factor(snapshot: Dict[str, Any]) -> float:
    vals = snapshot.get("traffic_speed_bands", {}).get("value", [])
    if not vals:
        return 1.0
    bands = []
    for row in vals:
        band = row.get("SpeedBand") or row.get("speedBand")
        if band is not None:
            try:
                bands.append(float(band))
            except Exception:
                pass
    if not bands:
        return 1.0
    avg_band = sum(bands) / len(bands)
    return max(0.85, 1.4 - 0.1 * avg_band)


def _incident_penalty(snapshot: Dict[str, Any]) -> float:
    vals = snapshot.get("traffic_incidents", {}).get("value", [])
    return float(len(vals))


def _vms_penalty(snapshot: Dict[str, Any]) -> float:
    vals = snapshot.get("vms", {}).get("value", [])
    return float(len(vals))


def build_adjusted_cost_matrix(base: Dict[str, Any], nodes: List[Dict[str, Any]], snapshot: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, Any]:
    time_minutes = np.array(base["time_minutes"], dtype=float)
    distance_km = np.array(base["distance_km"], dtype=float)

    speed_factor = _speed_penalty_factor(snapshot)
    incident_count = _incident_penalty(snapshot)
    vms_count = _vms_penalty(snapshot)

    adjusted_time = time_minutes * speed_factor

    incident_term = weights.get("incident_penalty", 0.0) * (incident_count / max(len(nodes), 1))
    vms_term = weights.get("vms_penalty", 0.0) * (vms_count / max(len(nodes), 1))
    speed_term = weights.get("speed_penalty", 0.0) * max(speed_factor - 1.0, 0.0)

    cost = (
        weights.get("travel_time", 1.0) * adjusted_time
        + weights.get("distance", 0.0) * distance_km
        + speed_term
        + incident_term
        + vms_term
    )

    return {
        "time_minutes": adjusted_time,
        "distance_km": distance_km,
        "cost": cost,
        "snapshot": snapshot,
        "speed_factor": speed_factor,
        "incident_count": incident_count,
        "vms_count": vms_count,
    }


def save_matrix_summary(path: str | Path, nodes: List[Dict[str, Any]], adjusted: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "num_nodes": len(nodes),
        "speed_factor": adjusted["speed_factor"],
        "incident_count": adjusted["incident_count"],
        "vms_count": adjusted["vms_count"],
        "mean_time_min": float(np.mean(adjusted["time_minutes"])),
        "mean_distance_km": float(np.mean(adjusted["distance_km"])),
        "mean_cost": float(np.mean(adjusted["cost"])),
    }
    with p.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)