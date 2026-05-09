"""Optional Vastu preference evaluation.

Vastu is treated as guidance only. Bylaw and safety constraints always remain
higher priority in the pipeline.
"""

from __future__ import annotations

from typing import Dict, List

VASTU_ROOM_PREFERENCES = {
    "entrance": {"north", "east", "northeast"},
    "living_room": {"north", "east", "northeast"},
    "kitchen": {"southeast", "east"},
    "master_bedroom": {"southwest", "south"},
    "bedroom": {"southwest", "west", "south"},
    "puja_room": {"northeast", "east"},
    "staircase": {"south", "west", "southwest"},
    "bathroom": {"west", "northwest", "south"},
    "toilet": {"west", "northwest", "south"},
}


def _resolve_room_key(room_type: str) -> str:
    room = (room_type or "").strip().lower()
    if "master" in room and "bed" in room:
        return "master_bedroom"
    if room in VASTU_ROOM_PREFERENCES:
        return room
    if "bed" in room:
        return "bedroom"
    if "bath" in room or "toilet" in room or "wc" in room:
        return "bathroom"
    return room


def evaluate_vastu_preferences(
    layout_zones: List[dict],
    plot_facing_direction: str,
    enabled: bool,
) -> Dict[str, object]:
    """Evaluate orientation preferences for the generated conceptual layout."""

    if not enabled:
        return {
            "enabled": False,
            "plot_facing_direction": plot_facing_direction,
            "score": None,
            "room_checks": [],
            "notes": [
                "Vastu checks were skipped because Vastu preference was not requested."
            ],
            "priority": [
                "bylaws",
                "safety_and_geometry",
                "architectural_feasibility",
                "vastu_preferences",
            ],
        }

    checks: List[dict] = []
    passed = 0
    total = 0

    for zone in layout_zones:
        room_type = str(zone.get("room_type", "")).strip().lower()
        orientation = str(zone.get("orientation", "")).strip().lower()

        key = _resolve_room_key(room_type)
        preferred = VASTU_ROOM_PREFERENCES.get(key)
        if not preferred:
            continue

        total += 1
        is_pass = orientation in preferred
        if is_pass:
            passed += 1

        checks.append(
            {
                "room": room_type,
                "floor": zone.get("floor", 0),
                "orientation": orientation,
                "vastu_preferred": sorted(preferred),
                "passed": is_pass,
                "note": (
                    f"{room_type} is aligned with Vastu preference."
                    if is_pass
                    else f"{room_type} orientation is sub-optimal for Vastu."
                ),
            }
        )

    score = round((passed / total) * 100.0, 1) if total else None

    notes: List[str] = []
    if total == 0:
        notes.append("No Vastu-mapped rooms were present in the generated layout.")
    elif passed == total:
        notes.append("All Vastu-mapped rooms satisfy preferred orientation guidance.")
    else:
        notes.append(
            "Some Vastu preferences could not be satisfied due to legal or geometric constraints."
        )

    notes.append(
        "Conflict resolution priority: bylaws > safety and geometry > feasibility > Vastu."
    )

    return {
        "enabled": True,
        "plot_facing_direction": plot_facing_direction,
        "score": score,
        "room_checks": checks,
        "notes": notes,
        "priority": [
            "bylaws",
            "safety_and_geometry",
            "architectural_feasibility",
            "vastu_preferences",
        ],
    }
