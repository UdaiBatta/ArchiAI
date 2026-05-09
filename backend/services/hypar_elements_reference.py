"""Reference export aligned with Hypar *Elements* library concepts.

The Hypar Elements API documents the C# model types used in Hypar's geometry stack
(Wall, Space, Floor, Model, Mass, etc.):

  https://hypar-io.github.io/Elements/api/Elements.html

That documentation is **not** the same as:

- the hypar.io web app "upload spreadsheet" flow (our CSV bridge), or
- a single public HTTP "upload this JSON" URL (that depends on Hypar product/API access).

This module produces a **small, explicit sidecar JSON** so developers can map Archi3D
layout zones toward Elements types (e.g. :class:`Space`, level grouping) when building
a plugin, a .NET importer, or a custom Hypar Function — without claiming full Elements
serialization (which requires the Elements runtime types and transforms).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ELEMENTS_API_ROOT = "https://hypar-io.github.io/Elements/api/Elements.html"


def build_elements_reference_payload(
    *,
    layout_zones: List[dict],
    floor_height_m: float,
    metadata: Dict[str, object],
    furniture_elements: Optional[List[dict]] = None,
) -> Dict[str, object]:
    """Build a documented handoff structure naming Elements concepts for each zone.

    ``kind`` values are labels for human/plugin mapping, not full Elements instances.
    """
    max_floor = max((int(z.get("floor", 0)) for z in layout_zones), default=0)
    levels = [
        {
            "index": level,
            "elevation_m": round(level * floor_height_m, 3),
            "elements_doc_anchor": "Elements has no single 'Level' class in the index; "
            "use elevation / Space placement — see Model and Space.",
        }
        for level in range(max_floor + 1)
    ]

    elements: List[Dict[str, object]] = []
    for zone in layout_zones:
        level = int(zone.get("floor", 0))
        w = float(zone.get("width_m", 0.0))
        d = float(zone.get("depth_m", 0.0))
        x = float(zone.get("x", 0.0))
        y = float(zone.get("y", 0.0))
        z = round(level * floor_height_m, 3)

        elements.append(
            {
                "kind": "Space",
                "hypar_elements_type": "Space",
                "hypar_doc": f"{ELEMENTS_API_ROOT} — Space: extruded occupiable region",
                "name": str(zone.get("room_type", "space")),
                "architectural_zone_id": zone.get("id"),
                "level_index": level,
                "origin_m": [x, y, z],
                "size_m": [w, d, floor_height_m],
                "note": "Map to Elements.Space with profile/boundary as your importer requires.",
            }
        )

    # Append furniture as FurnitureElement records
    for item in (furniture_elements or []):
        elements.append(
            {
                "kind": "FurnitureElement",
                "hypar_elements_type": item.get("hypar_elements_type", "Mass"),
                "hypar_doc": item.get("hypar_doc", f"{ELEMENTS_API_ROOT} — Mass"),
                "name": item.get("type", "Furniture"),
                "architectural_zone_id": item.get("zone_id"),
                "level_index": item.get("floor", 0),
                "origin_m": item.get("origin_m", [0, 0, 0]),
                "size_m": item.get("size_m", [0, 0, 0]),
                "rotation_deg": item.get("rotation_deg", 0.0),
                "note": item.get("note", ""),
            }
        )

    return {
        "format": "archi3d.elements_reference/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documentation": {
            "hypar_elements_api": ELEMENTS_API_ROOT,
            "description": (
                "Hypar Elements defines geometric model types (Wall, Space, Floor, Model, …). "
                "Use this file as a bridge for custom importers; it is not a complete Elements Model serialization."
            ),
        },
        "metadata": metadata,
        "plot_dimensions_m": (metadata or {}).get("plot_dimensions_m", {}),
        "buildable_footprint_m": (metadata or {}).get("buildable_footprint_m", {}),
        "levels_hint": levels,
        "elements": elements,
        "space_count": sum(1 for e in elements if e["kind"] == "Space"),
        "furniture_count": sum(1 for e in elements if e["kind"] == "FurnitureElement"),
    }


def write_hypar_elements_reference_json(
    *,
    layout_zones: List[dict],
    floor_height_m: float,
    metadata: Dict[str, object],
    outputs_dir: Path,
    session_seed: str,
    furniture_elements: Optional[List[dict]] = None,
) -> str:
    payload = build_elements_reference_payload(
        layout_zones=layout_zones,
        floor_height_m=floor_height_m,
        metadata=metadata,
        furniture_elements=furniture_elements,
    )
    outputs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"hypar_elements_ref_{session_seed}.json"
    target_path = outputs_dir / filename
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return filename
