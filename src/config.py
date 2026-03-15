from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    required = ["onemap_email", "onemap_password", "lta_account_key", "study_area", "fleet", "cost_weights", "ga_bo"]
    for key in required:
        if key not in cfg:
            raise KeyError(f"Missing required config key: {key}")
    return cfg