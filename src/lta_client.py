from __future__ import annotations

from typing import Any, Dict

import requests


class LTAClient:
    BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice"

    def __init__(self, account_key: str, timeout: int = 45):
        self.account_key = account_key
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "AccountKey": self.account_key,
            "accept": "application/json",
        }

    def _get(self, endpoint: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def fetch_snapshot(self, use_live_api: bool = False) -> Dict[str, Any]:
        if not use_live_api:
            return {
                "source": "mock",
                "traffic_images": {"value": []},
                "traffic_incidents": {"value": []},
                "traffic_speed_bands": {
                    "value": [
                        {"RoadName": "A", "SpeedBand": 3},
                        {"RoadName": "B", "SpeedBand": 2},
                        {"RoadName": "C", "SpeedBand": 4},
                    ]
                },
                "vms": {"value": []},
            }

        snapshot = {
            "source": "lta_live",
            "traffic_images": self._get("Traffic-Imagesv2"),
            "traffic_incidents": self._get("TrafficIncidents"),
            "traffic_speed_bands": self._get("v4/TrafficSpeedBands"),
            "vms": self._get("VMS"),
        }
        return snapshot