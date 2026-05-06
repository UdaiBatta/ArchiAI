"""Geometry conversion and Hypar-compatible payload writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def build_hypar_payload(
    layout_zones: List[dict],
    floor_height_m: float,
    metadata: Dict[str, object],
) -> Dict[str, object]:
    max_floor = max((int(zone.get("floor", 0)) for zone in layout_zones), default=0)

    levels = [
        {
            "level": level,
            "elevation_m": round(level * floor_height_m, 3),
            "height_m": round(floor_height_m, 3),
        }
        for level in range(max_floor + 1)
    ]

    zones = []
    for zone in layout_zones:
        level = int(zone.get("floor", 0))
        zones.append(
            {
                "id": zone.get("id"),
                "room_type": zone.get("room_type"),
                "level": level,
                "orientation": zone.get("orientation"),
                "origin_m": [
                    float(zone.get("x", 0.0)),
                    float(zone.get("y", 0.0)),
                    round(level * floor_height_m, 3),
                ],
                "size_m": [
                    float(zone.get("width_m", 0.0)),
                    float(zone.get("depth_m", 0.0)),
                    round(floor_height_m, 3),
                ],
            }
        )

    return {
        "schema": "archi3d-hypar-concept/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "levels": levels,
        "zones": zones,
    }


def write_hypar_json(
    payload: Dict[str, object],
    outputs_dir: Path,
    session_seed: str,
) -> str:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"hypar_{session_seed}.json"
    target_path = outputs_dir / filename
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return filename
