"""Geometry conversion and Hypar-compatible payload writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def build_hypar_payload(
    layout_zones: List[dict],
    floor_height_m: float,
    metadata: Dict[str, object],
    furniture_elements: Optional[List[dict]] = None,
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

    # Index furniture by zone_id for quick lookup
    furniture_by_zone: Dict[str, List[dict]] = {}
    for item in (furniture_elements or []):
        zid = str(item.get("zone_id", ""))
        furniture_by_zone.setdefault(zid, []).append(item)

    zones = []
    for zone in layout_zones:
        level = int(zone.get("floor", 0))
        zone_id = zone.get("id", "")
        zones.append(
            {
                "id": zone_id,
                "room_type": zone.get("room_type"),
                "level": level,
                "orientation": zone.get("orientation"),
                "street_facing": zone.get("street_facing", False),
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
                "area_sqm": zone.get("area_sqm"),
                "target_area_sqm": zone.get("target_area_sqm"),
                "furniture": furniture_by_zone.get(zone_id, []),
            }
        )

    return {
        "schema": "archi3d-hypar-concept/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "plot_dimensions_m": (metadata or {}).get("plot_dimensions_m", {}),
        "buildable_footprint_m": (metadata or {}).get("buildable_footprint_m", {}),
        "levels": levels,
        "zones": zones,
        "furniture_element_count": len(furniture_elements or []),
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
