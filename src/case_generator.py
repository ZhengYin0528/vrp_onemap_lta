from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List


CLEMENTI_CANDIDATES = [
    {"id": "BIN_001", "address": "416 Clementi Avenue 1, Singapore", "lat": 1.3196, "lon": 103.7650},
    {"id": "BIN_002", "address": "421 Clementi Avenue 1, Singapore", "lat": 1.3209, "lon": 103.7661},
    {"id": "BIN_003", "address": "435 Clementi Avenue 3, Singapore", "lat": 1.3148, "lon": 103.7659},
    {"id": "BIN_004", "address": "442 Clementi Avenue 3, Singapore", "lat": 1.3138, "lon": 103.7669},
    {"id": "BIN_005", "address": "450 Clementi Avenue 3, Singapore", "lat": 1.3125, "lon": 103.7681},
    {"id": "BIN_006", "address": "301 Clementi Avenue 4, Singapore", "lat": 1.3212, "lon": 103.7719},
    {"id": "BIN_007", "address": "320 Clementi Avenue 4, Singapore", "lat": 1.3193, "lon": 103.7727},
    {"id": "BIN_008", "address": "342 Clementi Avenue 5, Singapore", "lat": 1.3181, "lon": 103.7694},
    {"id": "BIN_009", "address": "347 Clementi Avenue 5, Singapore", "lat": 1.3175, "lon": 103.7704},
    {"id": "BIN_010", "address": "608 Clementi West Street 1, Singapore", "lat": 1.3048, "lon": 103.7598},
    {"id": "BIN_011", "address": "720 Clementi West Street 2, Singapore", "lat": 1.3046, "lon": 103.7641},
    {"id": "BIN_012", "address": "725 Clementi West Street 2, Singapore", "lat": 1.3040, "lon": 103.7653},
]

DEFAULT_DEPOT = {
    "id": "DEPOT",
    "address": "3151 Commonwealth Avenue West, Singapore",
    "lat": 1.3153,
    "lon": 103.7640,
}

DEFAULT_INCINERATOR = {
    "id": "INCINERATOR",
    "address": "Tuas South Avenue 3, Singapore",
    "lat": 1.2998,
    "lon": 103.6290,
}


def _geocode_address(onemap_client: Any, address: str, use_live_api: bool, fallback_lat: float, fallback_lon: float) -> Dict[str, float]:
    if not use_live_api:
        return {"lat": fallback_lat, "lon": fallback_lon}

    try:
        result = onemap_client.search(address)
        rows = result.get("results", [])
        if rows:
            row = rows[0]
            lat = float(row["LATITUDE"])
            lon = float(row["LONGITUDE"])
            return {"lat": lat, "lon": lon}
    except Exception as e:
        print(f"[WARN] OneMap geocoding failed for '{address}', using fallback coordinates. Reason: {e}")

    return {"lat": fallback_lat, "lon": fallback_lon}


def generate_case(cfg: Dict[str, Any], onemap_client: Any, use_live_api: bool = False) -> Dict[str, Any]:
    rng = random.Random(cfg["ga_bo"].get("ga_seed", 42))
    fleet = cfg["fleet"]
    num_bins = min(fleet["num_bins"], len(CLEMENTI_CANDIDATES))

    selected = CLEMENTI_CANDIDATES[:]
    rng.shuffle(selected)
    selected = selected[:num_bins]

    depot_geo = _geocode_address(
        onemap_client, DEFAULT_DEPOT["address"], use_live_api, DEFAULT_DEPOT["lat"], DEFAULT_DEPOT["lon"]
    )
    inc_geo = _geocode_address(
        onemap_client, DEFAULT_INCINERATOR["address"], use_live_api, DEFAULT_INCINERATOR["lat"], DEFAULT_INCINERATOR["lon"]
    )

    bins: List[Dict[str, Any]] = []
    for item in selected:
        geo = _geocode_address(
            onemap_client, item["address"], use_live_api, item["lat"], item["lon"]
        )
        cap = rng.uniform(fleet["bin_capacity_min_liters"], fleet["bin_capacity_max_liters"])
        fill = rng.uniform(fleet["fill_fraction_min"], fleet["fill_fraction_max"])
        demand = cap * fill

        bins.append({
            "id": item["id"],
            "address": item["address"],
            "lat": round(geo["lat"], 7),
            "lon": round(geo["lon"], 7),
            "bin_capacity_liters": round(cap, 2),
            "fill_fraction": round(fill, 3),
            "demand_liters": round(demand, 2),
        })

    case = {
        "study_area": {
            "name": "Clementi HDB proxy study area",
            "description": "Real residential proxy nodes in Clementi replacing random coordinate generation."
        },
        "depot": {
            "id": DEFAULT_DEPOT["id"],
            "address": DEFAULT_DEPOT["address"],
            "lat": round(depot_geo["lat"], 7),
            "lon": round(depot_geo["lon"], 7),
        },
        "incinerator": {
            "id": DEFAULT_INCINERATOR["id"],
            "address": DEFAULT_INCINERATOR["address"],
            "lat": round(inc_geo["lat"], 7),
            "lon": round(inc_geo["lon"], 7),
        },
        "fleet": fleet,
        "bins": bins,
    }
    return case


def generate_small_validation_case(cfg: Dict[str, Any], onemap_client: Any, use_live_api: bool = False) -> Dict[str, Any]:
    rng = random.Random(123)
    selected = CLEMENTI_CANDIDATES[:5]

    depot_geo = _geocode_address(
        onemap_client, DEFAULT_DEPOT["address"], use_live_api, DEFAULT_DEPOT["lat"], DEFAULT_DEPOT["lon"]
    )
    inc_geo = _geocode_address(
        onemap_client, DEFAULT_INCINERATOR["address"], use_live_api, DEFAULT_INCINERATOR["lat"], DEFAULT_INCINERATOR["lon"]
    )

    bins: List[Dict[str, Any]] = []
    for item in selected:
        geo = _geocode_address(
            onemap_client, item["address"], use_live_api, item["lat"], item["lon"]
        )
        cap = rng.uniform(660, 1100)
        fill = rng.uniform(0.45, 0.75)
        demand = cap * fill

        bins.append({
            "id": item["id"],
            "address": item["address"],
            "lat": round(geo["lat"], 7),
            "lon": round(geo["lon"], 7),
            "bin_capacity_liters": round(cap, 2),
            "fill_fraction": round(fill, 3),
            "demand_liters": round(demand, 2),
        })

    case = {
        "study_area": {
            "name": "Small validation case",
            "description": "Tiny exact-solvable case for brute-force validation."
        },
        "depot": {
            "id": DEFAULT_DEPOT["id"],
            "address": DEFAULT_DEPOT["address"],
            "lat": round(depot_geo["lat"], 7),
            "lon": round(depot_geo["lon"], 7),
        },
        "incinerator": {
            "id": DEFAULT_INCINERATOR["id"],
            "address": DEFAULT_INCINERATOR["address"],
            "lat": round(inc_geo["lat"], 7),
            "lon": round(inc_geo["lon"], 7),
        },
        "fleet": {
            "num_trucks": 1,
            "truck_capacity_liters": 5000,
            "num_bins": 5,
            "bin_capacity_min_liters": 660,
            "bin_capacity_max_liters": 1100,
            "fill_fraction_min": 0.45,
            "fill_fraction_max": 0.75,
        },
        "bins": bins,
    }
    return case


def save_case(case: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)