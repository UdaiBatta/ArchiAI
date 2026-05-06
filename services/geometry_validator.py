"""Deterministic geometry validation checks for conceptual layouts.

Includes overlap detection, minimum-side enforcement, and vertical
core continuity validation for stair_core / service_shaft zones.
"""

from __future__ import annotations

from typing import Dict, List

# Room types that must maintain perfect vertical alignment.
_VERTICAL_CORE_TYPES: frozenset[str] = frozenset({"stair_core", "service_shaft"})


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


def _footprint_key(zone: dict) -> tuple:
    """Return a hashable (x, y, width, depth) tuple for a zone."""
    return (
        round(float(zone.get("x", 0.0)), 3),
        round(float(zone.get("y", 0.0)), 3),
        round(float(zone.get("width_m", 0.0)), 3),
        round(float(zone.get("depth_m", 0.0)), 3),
    )


# ── Vertical core continuity ────────────────────────────────────────

def validate_vertical_core_continuity(
    layout_zones: List[dict],
) -> Dict[str, object]:
    """Check that every vertical-core zone has an identical footprint on every floor.

    For each core room_type (``stair_core``, ``service_shaft``), the
    (x, y, width_m, depth_m) on Floor 0 is treated as the reference.
    Any upper-floor zone whose footprint deviates is flagged as an error.

    Returns
    -------
    dict
        ``passed`` (bool), ``issues`` (list of dicts describing mismatches),
        and ``reference_footprints`` (the Floor-0 reference for each core type).
    """
    # Collect core zones grouped by room_type → floor → zone(s).
    cores_by_type: Dict[str, Dict[int, list]] = {}
    for zone in layout_zones:
        rt = str(zone.get("room_type", ""))
        if rt not in _VERTICAL_CORE_TYPES:
            continue
        floor = int(zone.get("floor", 0))
        cores_by_type.setdefault(rt, {}).setdefault(floor, []).append(zone)

    issues: List[dict] = []
    reference_footprints: Dict[str, tuple] = {}

    for core_type, floors_map in cores_by_type.items():
        ref_zones = floors_map.get(0)
        if not ref_zones:
            issues.append({
                "core_type": core_type,
                "floor": 0,
                "message": f"No {core_type} zone found on Floor 0 to use as reference.",
            })
            continue

        ref_fp = _footprint_key(ref_zones[0])
        reference_footprints[core_type] = ref_fp

        for floor_num in sorted(floors_map):
            if floor_num == 0:
                continue
            for zone in floors_map[floor_num]:
                zone_fp = _footprint_key(zone)
                if zone_fp != ref_fp:
                    issues.append({
                        "core_type": core_type,
                        "floor": floor_num,
                        "zone_id": zone.get("id"),
                        "expected": {"x": ref_fp[0], "y": ref_fp[1], "width_m": ref_fp[2], "depth_m": ref_fp[3]},
                        "actual": {"x": zone_fp[0], "y": zone_fp[1], "width_m": zone_fp[2], "depth_m": zone_fp[3]},
                        "message": (
                            f"{core_type} on Floor {floor_num} does not match Floor 0 footprint."
                        ),
                    })

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "reference_footprints": reference_footprints,
    }


# ── Main validator ───────────────────────────────────────────────────

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

    # ── Vertical core continuity ──────────────────────────────────
    core_result = validate_vertical_core_continuity(layout_zones)
    checks.append(
        {
            "name": "Vertical core continuity",
            "passed": core_result["passed"],
            "severity": "error",
            "message": (
                "All vertical cores (stair_core, service_shaft) are aligned across floors."
                if core_result["passed"]
                else f"Found {len(core_result['issues'])} vertical core misalignment(s)."
            ),
        }
    )

    overall_passed = all(check["passed"] for check in checks if check["severity"] == "error")

    return {
        "valid": overall_passed,
        "checks": checks,
        "overlap_issues": overlap_issues,
        "undersized_issues": undersized_issues,
        "core_continuity": core_result,
    }
