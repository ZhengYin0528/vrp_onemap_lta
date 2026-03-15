from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .utils import haversine_km

Coord = Tuple[float, float]


class OneMapClient:
    AUTH_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"
    ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"
    SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"

    def __init__(self, email: str, password: str, cache_dir: str | Path = ".cache", timeout: int = 12):
        self.email = email
        self.password = password
        self.timeout = timeout
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._token: Optional[str] = None

    def authenticate(self) -> str:
        payload = {"email": self.email, "password": self.password}
        r = requests.post(self.AUTH_URL, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token") or data.get("accessToken")
        if not token:
            raise RuntimeError(f"OneMap auth failed: {data}")
        self._token = token
        return token

    def _auth_header(self) -> Dict[str, str]:
        if not self._token:
            self.authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    def search(self, query: str, page_num: int = 1) -> Dict[str, Any]:
        params = {
            "searchVal": query,
            "returnGeom": "Y",
            "getAddrDetails": "Y",
            "pageNum": page_num,
        }
        r = requests.get(self.SEARCH_URL, params=params, headers=self._auth_header(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def route(self, start: Coord, end: Coord, route_type: str = "drive") -> Dict[str, Any]:
        params = {
            "start": f"{start[0]},{start[1]}",
            "end": f"{end[0]},{end[1]}",
            "routeType": route_type,
        }

        try:
            r = requests.get(
                self.ROUTE_URL,
                params=params,
                headers=self._auth_header(),
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"OneMap request exception: {e}")

        if not r.ok:
            raise RuntimeError(
                f"OneMap route failed.\n"
                f"URL: {r.url}\n"
                f"Status: {r.status_code}\n"
                f"Response: {r.text}"
            )

        try:
            data = r.json()
        except Exception as e:
            raise RuntimeError(f"OneMap returned non-JSON response: {e}\nRaw text: {r.text}")

        if isinstance(data, dict) and data.get("status") in ("error", "fail"):
            raise RuntimeError(f"OneMap route failed: {data}")

        return data

    @staticmethod
    def _decode_polyline(encoded: str, precision: int = 5) -> List[Coord]:
        """
        Decode Google/Mapbox-style encoded polyline into [(lat, lon), ...]
        """
        if not encoded:
            return []

        coords: List[Coord] = []
        index = 0
        lat = 0
        lon = 0
        factor = 10 ** precision

        while index < len(encoded):
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat

            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            dlon = ~(result >> 1) if (result & 1) else (result >> 1)
            lon += dlon

            coords.append((lat / factor, lon / factor))

        return coords

    @staticmethod
    def parse_route_geometry(route_json: Dict[str, Any], start: Coord | None = None, end: Coord | None = None) -> Tuple[List[Coord], bool]:
        """
        Returns:
            coords: list of (lat, lon)
            is_fallback: whether this geometry is only an approximate straight-line fallback
        """
        is_fallback = bool(route_json.get("mock", False))

        # Case 1: OneMap encoded polyline string
        for key in ("route_geometry", "routeGeometry"):
            geom = route_json.get(key)
            if isinstance(geom, str) and geom.strip():
                try:
                    coords = OneMapClient._decode_polyline(geom.strip())
                    if len(coords) >= 2:
                        return coords, is_fallback
                except Exception:
                    pass

        # Case 2: already a list of coordinates
        for key in ("route_geometry", "routeGeometry"):
            geom = route_json.get(key)
            if isinstance(geom, list) and geom:
                coords: List[Coord] = []
                for item in geom:
                    if isinstance(item, str):
                        parts = item.split(",")
                        if len(parts) == 2:
                            a, b = map(float, parts)
                            # try lon,lat first
                            if abs(a) > 20 and abs(b) < 20:
                                coords.append((b, a))
                            else:
                                coords.append((a, b))
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        a, b = float(item[0]), float(item[1])
                        if abs(a) > 20 and abs(b) < 20:
                            coords.append((b, a))
                        else:
                            coords.append((a, b))
                    elif isinstance(item, dict):
                        if {"lat", "lon"}.issubset(item):
                            coords.append((float(item["lat"]), float(item["lon"])))
                        elif {"latitude", "longitude"}.issubset(item):
                            coords.append((float(item["latitude"]), float(item["longitude"])))
                if len(coords) >= 2:
                    return coords, is_fallback

        # Case 3: fallback
        if start and end:
            return [start, end], True

        return [], True

    @staticmethod
    def parse_time_minutes(route_json: Dict[str, Any], fallback_start: Coord | None = None, fallback_end: Coord | None = None) -> float:
        for key in ("route_summary", "routeSummary", "summary"):
            summary = route_json.get(key)
            if isinstance(summary, dict):
                for time_key in ("total_time", "totalTime", "time"):
                    if time_key in summary:
                        val = float(summary[time_key])
                        return val / 60.0 if val > 1000 else val
        for key in ("total_time", "totalTime", "time"):
            if key in route_json:
                val = float(route_json[key])
                return val / 60.0 if val > 1000 else val
        if fallback_start and fallback_end:
            return haversine_km(fallback_start, fallback_end) / 30.0 * 60.0
        raise RuntimeError("Unable to parse route travel time.")

    @staticmethod
    def parse_distance_km(route_json: Dict[str, Any], fallback_start: Coord | None = None, fallback_end: Coord | None = None) -> float:
        for key in ("route_summary", "routeSummary", "summary"):
            summary = route_json.get(key)
            if isinstance(summary, dict):
                for dist_key in ("total_distance", "totalDistance", "distance"):
                    if dist_key in summary:
                        val = float(summary[dist_key])
                        return val / 1000.0 if val > 1000 else val
        for key in ("total_distance", "totalDistance", "distance"):
            if key in route_json:
                val = float(route_json[key])
                return val / 1000.0 if val > 1000 else val
        if fallback_start and fallback_end:
            return haversine_km(fallback_start, fallback_end)
        raise RuntimeError("Unable to parse route distance.")

    def route_cached(self, start: Coord, end: Coord, route_type: str = "drive", use_live_api: bool = False) -> Dict[str, Any]:
        key = f"{route_type}_{start[0]:.6f}_{start[1]:.6f}_{end[0]:.6f}_{end[1]:.6f}".replace(".", "p")
        cache_file = self.cache_dir / f"{key}.json"

        if cache_file.exists():
            with cache_file.open("r", encoding="utf-8") as f:
                return json.load(f)

        def fallback_data(reason: str) -> Dict[str, Any]:
            distance_km = haversine_km(start, end) * 1.25
            time_min = distance_km / 28.0 * 60.0
            data = {
                "summary": {"distance": distance_km, "time": time_min},
                "route_geometry": [
                    [start[0], start[1]],
                    [end[0], end[1]],
                ],
                "mock": True,
                "fallback_reason": reason,
            }
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data

        if use_live_api:
            try:
                data = self.route(start, end, route_type=route_type)
                with cache_file.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                time.sleep(0.05)
                return data
            except Exception as e:
                print(f"[WARN] OneMap routing failed for {start} -> {end}")
                print(f"[WARN] Falling back to approximate route. Reason: {e}")
                return fallback_data(str(e))

        return fallback_data("offline_mode")