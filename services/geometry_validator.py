"""Deterministic geometry validation checks for conceptual layouts."""

from __future__ import annotations

from typing import Dict, List


def _rectangles_overlap(a: dict, b: dict) -> bool:
    ax1 = float(a.get("x", 0.0))
    ay1 = float(a.get("y", 0.0))
    ax2 = ax1 + float(a.get("width_m", 0.0))
    ay2 = ay1 + float(a.get("depth_m", 0.0))

    bx1 = float(b.get("x", 0.0))
    by1 = float(b.get("y", 0.0))
    bx2 = bx1 + float(b.get("width_m", 0.0))
    by2 = by1 + float(b.get("depth_m", 0.0))

    # Touching edges are allowed; strict overlap only.
    separated = ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1
    return not separated


def validate_layout_geometry(
    layout_zones: List[dict],
    min_room_side_m: float = 1.8,
) -> Dict[str, object]:
    checks: List[dict] = []
    overlap_issues: List[dict] = []
    undersized_issues: List[dict] = []

    zones_by_floor: Dict[int, List[dict]] = {}
    for zone in layout_zones:
        floor = int(zone.get("floor", 0))
        zones_by_floor.setdefault(floor, []).append(zone)

    for floor, zones in zones_by_floor.items():
        for i in range(len(zones)):
            zone = zones[i]
            width = float(zone.get("width_m", 0.0))
            depth = float(zone.get("depth_m", 0.0))
            if width < min_room_side_m or depth < min_room_side_m:
                undersized_issues.append(
                    {
                        "floor": floor,
                        "zone_id": zone.get("id"),
                        "room_type": zone.get("room_type"),
                        "width_m": width,
                        "depth_m": depth,
                        "minimum_m": min_room_side_m,
                    }
                )

            for j in range(i + 1, len(zones)):
                other = zones[j]
                if _rectangles_overlap(zone, other):
                    overlap_issues.append(
                        {
                            "floor": floor,
                            "zone_a": zone.get("id"),
                            "zone_b": other.get("id"),
                            "room_a": zone.get("room_type"),
                            "room_b": other.get("room_type"),
                        }
                    )

    overlap_passed = len(overlap_issues) == 0
    size_passed = len(undersized_issues) == 0

    checks.append(
        {
            "name": "No zone overlap",
            "passed": overlap_passed,
            "severity": "error",
            "message": (
                "No overlaps detected in floor layouts."
                if overlap_passed
                else f"Found {len(overlap_issues)} overlapping zone pairs."
            ),
        }
    )
    checks.append(
        {
            "name": "Minimum room side",
            "passed": size_passed,
            "severity": "warning",
            "message": (
                f"All zones meet the minimum side of {min_room_side_m}m."
                if size_passed
                else f"Found {len(undersized_issues)} zones below minimum side {min_room_side_m}m."
            ),
        }
    )

    overall_passed = all(check["passed"] for check in checks if check["severity"] == "error")

    return {
        "valid": overall_passed,
        "checks": checks,
        "overlap_issues": overlap_issues,
        "undersized_issues": undersized_issues,
    }
