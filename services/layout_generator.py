"""Heuristic conceptual layout generation.

Generates simple rectangular zoning blocks constrained by deterministic
bylaw outputs from the compliance report.

Vertical-core rooms (stair_core, service_shaft) are locked on Floor 0
and propagated with identical (x, y, w, h) to every upper floor.
Corridor/circulation zones must maintain a minimum width of 1.2 m.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections import Counter
from typing import Dict, List

from services.bylaw_loader import BylawRuleset

# ── Constants ─────────────────────────────────────────────────────────

# Minimum clear width for any corridor or circulation zone (metres).
MIN_CORRIDOR_WIDTH_M: float = 1.2

# Room types that must maintain exact vertical alignment across floors.
VERTICAL_CORE_TYPES: frozenset[str] = frozenset({"stair_core", "service_shaft"})


SLOT_NEIGHBORS = {
    0: {1, 2},
    1: {0, 3},
    2: {0, 3},
    3: {1, 2},
}

ROOM_ADJACENCY_WEIGHTS = {
    ("living_room", "kitchen"): 3.0,
    ("living_room", "staircase"): 2.5,
    ("bedroom", "bathroom"): 2.0,
    ("staircase", "circulation"): 1.5,
    ("parking", "staircase"): 1.5,
    ("kitchen", "dining"): 1.0,
    ("living_room", "balcony"): 1.0,
}

ROOM_ORIENTATION_PREFERENCES = {
    "living_room": {"northwest", "northeast"},
    "kitchen": {"southeast", "northeast"},
    "bedroom": {"southwest", "northwest", "southeast"},
    "bathroom": {"southwest", "northwest"},
    "staircase": {"northwest", "southwest", "southeast", "northeast"},
    "parking": {"southwest", "southeast"},
    "puja_room": {"northeast", "northwest"},
}


def _expand_room_program(parsed_input: Dict[str, object]) -> List[str]:
    requested_rooms = parsed_input.get("rooms") or []
    rooms = [str(room).strip().lower() for room in requested_rooms if str(room).strip()]

    if not rooms:
        # Reasonable defaults for conceptual planning.
        rooms = ["living_room", "kitchen", "bedroom", "bedroom", "bathroom", "staircase"]

    room_counter = Counter(rooms)

    if "living_room" not in room_counter:
        rooms.insert(0, "living_room")
    if "kitchen" not in room_counter:
        rooms.append("kitchen")
    if "staircase" not in room_counter:
        rooms.append("staircase")

    preferences = parsed_input.get("preferences") or {}
    if isinstance(preferences, dict) and preferences.get("parking"):
        if "parking" not in room_counter:
            rooms.insert(0, "parking")

    if isinstance(preferences, dict) and preferences.get("puja_room"):
        rooms.append("puja_room")

    return rooms


# ── Vertical-core helpers ─────────────────────────────────────────────

def _allocate_core_footprint(
    slot: Dict[str, float],
    fraction: float = 0.4,
    anchor: str = "top-left",
) -> Dict[str, float]:
    """Carve a rectangular sub-region from *slot* for a vertical core.

    Parameters
    ----------
    slot:
        The quadrant dict produced by ``_quadrant_slots``.
    fraction:
        Fraction of the slot's *smaller* dimension to use for the core.
    anchor:
        Where inside the slot the core should sit.
    """
    sw = float(slot["width_m"])
    sd = float(slot["depth_m"])
    side = min(sw, sd) * fraction
    side = max(side, MIN_CORRIDOR_WIDTH_M)  # Never below corridor minimum.

    # Anchor inside slot
    sx = float(slot["x"])
    sy = float(slot["y"])
    if anchor == "top-left":
        cx, cy = sx, sy + sd - side
    elif anchor == "top-right":
        cx, cy = sx + sw - side, sy + sd - side
    elif anchor == "bottom-right":
        cx, cy = sx + sw - side, sy
    else:  # bottom-left (default fallback)
        cx, cy = sx, sy

    return {
        "x": round(cx, 3),
        "y": round(cy, 3),
        "width_m": round(side, 3),
        "depth_m": round(side, 3),
    }


def _build_fixed_cores(
    slots: List[Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    """Return floor-0 footprints for ``stair_core`` and ``service_shaft``.

    Stair core is placed in the *last* quadrant (southeast by default).
    Service shaft is placed in the *third* quadrant (southwest).
    Both inherit the slot's coordinates and are sized as a fraction of the
    slot so they don't dominate the floor plan.
    """
    stair_slot = slots[-1] if slots else slots[0]
    shaft_slot = slots[-2] if len(slots) >= 2 else stair_slot

    return {
        "stair_core": _allocate_core_footprint(stair_slot, fraction=0.4, anchor="bottom-right"),
        "service_shaft": _allocate_core_footprint(shaft_slot, fraction=0.3, anchor="bottom-left"),
    }


# ── Corridor width check ──────────────────────────────────────────────

def check_corridor_widths(
    zones: List[dict],
    min_width_m: float = MIN_CORRIDOR_WIDTH_M,
) -> Dict[str, object]:
    """Return a validation result for corridor/circulation width.

    Any zone whose ``room_type`` is ``corridor`` or ``circulation`` must
    have *both* ``width_m`` and ``depth_m`` >= *min_width_m*.
    """
    corridor_types = {"corridor", "circulation"}
    issues: List[dict] = []

    for zone in zones:
        rt = str(zone.get("room_type", "")).strip().lower()
        if rt not in corridor_types:
            continue
        w = float(zone.get("width_m", 0.0))
        d = float(zone.get("depth_m", 0.0))
        narrow_side = min(w, d)
        if narrow_side < min_width_m:
            issues.append({
                "zone_id": zone.get("id"),
                "floor": zone.get("floor"),
                "room_type": rt,
                "width_m": w,
                "depth_m": d,
                "narrow_side_m": round(narrow_side, 3),
                "minimum_m": min_width_m,
            })

    return {
        "passed": len(issues) == 0,
        "min_corridor_width_m": min_width_m,
        "issues": issues,
    }


def _normalize_room_type(room_type: str) -> str:
    room = str(room_type or "").strip().lower()
    if "bed" in room:
        return "bedroom"
    if "bath" in room or "toilet" in room or "wash" in room:
        return "bathroom"
    return room


def _pair_key(room_a: str, room_b: str) -> tuple[str, str]:
    return tuple(sorted((_normalize_room_type(room_a), _normalize_room_type(room_b))))


def _entry_orientations_for_plot_facing(plot_facing_direction: str) -> set[str]:
    mapping = {
        "north": {"northwest", "northeast"},
        "south": {"southwest", "southeast"},
        "east": {"northeast", "southeast"},
        "west": {"northwest", "southwest"},
        "northeast": {"northeast"},
        "northwest": {"northwest"},
        "southeast": {"southeast"},
        "southwest": {"southwest"},
    }
    return mapping.get(str(plot_facing_direction or "").lower(), {"northwest", "northeast"})


def _compute_coverage_limited_footprint(
    buildable_width_m: float,
    buildable_depth_m: float,
    plot_area_sqm: float,
    max_plot_coverage_pct: float,
) -> Dict[str, float]:
    full_buildable_area = buildable_width_m * buildable_depth_m
    if full_buildable_area <= 0 or plot_area_sqm <= 0:
        return {
            "width_m": 0.0,
            "depth_m": 0.0,
            "area_sqm": 0.0,
            "scale": 0.0,
        }

    max_coverage_area = plot_area_sqm * (max_plot_coverage_pct / 100.0)
    allowed_area = min(full_buildable_area, max_coverage_area)

    scale = math.sqrt(allowed_area / full_buildable_area) if full_buildable_area > 0 else 0.0
    width_m = buildable_width_m * scale
    depth_m = buildable_depth_m * scale

    return {
        "width_m": round(width_m, 3),
        "depth_m": round(depth_m, 3),
        "area_sqm": round(allowed_area, 3),
        "scale": round(scale, 4),
    }


def _quadrant_slots(width_m: float, depth_m: float) -> List[Dict[str, float]]:
    half_w = width_m / 2.0
    half_d = depth_m / 2.0

    return [
        {"x": 0.0, "y": half_d, "width_m": half_w, "depth_m": half_d, "orientation": "northwest"},
        {"x": half_w, "y": half_d, "width_m": half_w, "depth_m": half_d, "orientation": "northeast"},
        {"x": 0.0, "y": 0.0, "width_m": half_w, "depth_m": half_d, "orientation": "southwest"},
        {"x": half_w, "y": 0.0, "width_m": half_w, "depth_m": half_d, "orientation": "southeast"},
    ]


def _take_first(room_queue: List[str], room_type: str) -> str | None:
    for idx, value in enumerate(room_queue):
        if value == room_type:
            return room_queue.pop(idx)
    return None


def _build_floor_program(
    room_queue: List[str],
    floor: int,
    slot_capacity: int,
    parking_requested: bool,
) -> List[str]:
    required = ["staircase"] if floor > 0 else ["living_room", "kitchen", "staircase"]
    if floor == 0 and parking_requested:
        required.insert(0, "parking")

    floor_program: List[str] = []
    for room_type in required:
        taken = _take_first(room_queue, room_type)
        if taken:
            floor_program.append(taken)
        elif room_type in {"staircase", "living_room", "kitchen"}:
            floor_program.append(room_type)

    while room_queue and len(floor_program) < slot_capacity:
        floor_program.append(room_queue.pop(0))

    while len(floor_program) < slot_capacity:
        floor_program.append("multi_use" if floor > 0 else "circulation")

    return floor_program[:slot_capacity]


def _candidate_score(
    room_type: str,
    slot_idx: int,
    assigned: Dict[int, str],
    slots: List[Dict[str, float]],
    floor: int,
    plot_facing_direction: str,
) -> float:
    score = 0.0
    normalized_room = _normalize_room_type(room_type)
    orientation = slots[slot_idx]["orientation"]

    room_preferences = ROOM_ORIENTATION_PREFERENCES.get(normalized_room, set())
    if orientation in room_preferences:
        score += 1.0

    if floor == 0 and normalized_room in {"living_room", "parking"}:
        if orientation in _entry_orientations_for_plot_facing(plot_facing_direction):
            score += 0.9

    for neighbor_idx in SLOT_NEIGHBORS.get(slot_idx, set()):
        neighbor_room = assigned.get(neighbor_idx)
        if not neighbor_room:
            continue
        pair_weight = ROOM_ADJACENCY_WEIGHTS.get(_pair_key(normalized_room, neighbor_room), 0.0)
        score += pair_weight * 1.2

    if normalized_room == "staircase":
        score += 0.4

    return score


def _assign_rooms_to_slots(
    floor_rooms: List[str],
    slots: List[Dict[str, float]],
    floor: int,
    plot_facing_direction: str,
) -> Dict[int, str]:
    remaining = list(floor_rooms)
    assigned: Dict[int, str] = {}

    for slot_idx in range(len(slots)):
        best_idx = 0
        best_score = float("-inf")

        for candidate_idx, candidate in enumerate(remaining):
            score = _candidate_score(
                room_type=candidate,
                slot_idx=slot_idx,
                assigned=assigned,
                slots=slots,
                floor=floor,
                plot_facing_direction=plot_facing_direction,
            )
            if score > best_score:
                best_score = score
                best_idx = candidate_idx

        assigned[slot_idx] = remaining.pop(best_idx)

    return assigned


def _shortest_path_steps(start: int, target: int) -> int:
    if start == target:
        return 0

    frontier = [(start, 0)]
    visited = {start}

    while frontier:
        node, steps = frontier.pop(0)
        for neighbor in SLOT_NEIGHBORS.get(node, set()):
            if neighbor in visited:
                continue
            if neighbor == target:
                return steps + 1
            visited.add(neighbor)
            frontier.append((neighbor, steps + 1))

    return 3


def _compute_layout_metrics(zones: List[dict]) -> Dict[str, object]:
    zones_by_floor: Dict[int, List[dict]] = defaultdict(list)
    for zone in zones:
        zones_by_floor[int(zone.get("floor", 0))].append(zone)

    floor_metrics: List[dict] = []

    for floor, floor_zones in sorted(zones_by_floor.items()):
        slots_by_room: Dict[str, List[int]] = defaultdict(list)
        for zone in floor_zones:
            room_type = _normalize_room_type(str(zone.get("room_type", "")))
            slot_idx = int(zone.get("slot_index", 0))
            slots_by_room[room_type].append(slot_idx)

        adjacency_possible = 0.0
        adjacency_satisfied = 0.0
        unmet_adjacencies: List[str] = []

        for (room_a, room_b), weight in ROOM_ADJACENCY_WEIGHTS.items():
            slots_a = slots_by_room.get(room_a, [])
            slots_b = slots_by_room.get(room_b, [])
            if not slots_a or not slots_b:
                continue

            adjacency_possible += weight
            satisfied = any(slot_b in SLOT_NEIGHBORS.get(slot_a, set()) for slot_a in slots_a for slot_b in slots_b)
            if satisfied:
                adjacency_satisfied += weight
            else:
                unmet_adjacencies.append(f"{room_a}-{room_b}")

        adjacency_score = 100.0 if adjacency_possible == 0 else (adjacency_satisfied / adjacency_possible) * 100.0

        anchor_slots = slots_by_room.get("living_room") or slots_by_room.get("parking")
        anchor = anchor_slots[0] if anchor_slots else int(floor_zones[0].get("slot_index", 0))

        target_slots: List[int] = []
        for target_room in ["kitchen", "staircase", "bathroom"]:
            target_slots.extend(slots_by_room.get(target_room, []))

        path_lengths = [
            min(_shortest_path_steps(anchor, target_slot), 3) for target_slot in target_slots
        ]
        if path_lengths:
            average_steps = sum(path_lengths) / len(path_lengths)
            circulation_score = max(0.0, 100.0 - max(0.0, average_steps - 1.0) * 30.0)
        else:
            circulation_score = 100.0

        floor_quality_score = round((0.65 * adjacency_score) + (0.35 * circulation_score), 1)
        floor_metrics.append(
            {
                "floor": floor,
                "adjacency_score": round(adjacency_score, 1),
                "circulation_score": round(circulation_score, 1),
                "layout_quality_score": floor_quality_score,
                "unmet_adjacencies": unmet_adjacencies,
            }
        )

    if floor_metrics:
        overall_quality = round(
            sum(item["layout_quality_score"] for item in floor_metrics) / len(floor_metrics),
            1,
        )
    else:
        overall_quality = 0.0

    return {
        "overall_layout_quality_score": overall_quality,
        "floor_metrics": floor_metrics,
    }


def generate_conceptual_layout(
    parsed_input: Dict[str, object],
    compliance_report: Dict[str, object],
    bylaws: BylawRuleset,
) -> Dict[str, object]:
    """Generate floor-wise conceptual zones under bylaw constraints.

    Vertical cores (``stair_core``, ``service_shaft``) are locked on
    Floor 0 and propagated to every upper floor with ``is_fixed=True``.
    Corridor / circulation zones are checked against
    :data:`MIN_CORRIDOR_WIDTH_M`.
    """

    buildable = compliance_report.get("buildable_area", {})
    buildable_width_m = float(buildable.get("buildable_width_m", 0.0) or 0.0)
    buildable_depth_m = float(buildable.get("buildable_depth_m", 0.0) or 0.0)
    plot_area_sqm = float(buildable.get("plot_area_sqm", 0.0) or 0.0)

    floors = max(1, int(compliance_report.get("adjusted_floors", parsed_input.get("num_floors", 1)) or 1))
    room_queue = _expand_room_program(parsed_input)

    footprint = _compute_coverage_limited_footprint(
        buildable_width_m=buildable_width_m,
        buildable_depth_m=buildable_depth_m,
        plot_area_sqm=plot_area_sqm,
        max_plot_coverage_pct=bylaws.max_plot_coverage_pct,
    )

    zones: List[dict] = []
    notes: List[str] = []

    if footprint["area_sqm"] <= 0:
        notes.append("Layout generation skipped because no buildable footprint is available.")
        return {
            "zones": [],
            "layout_notes": notes,
            "footprint": footprint,
        }

    if footprint["scale"] < 1.0:
        notes.append(
            "Footprint scaled down from full buildable area to satisfy plot coverage constraints."
        )

    slots = _quadrant_slots(footprint["width_m"], footprint["depth_m"])
    zone_counter = 0

    preferences = parsed_input.get("preferences") or {}
    parking_requested = bool(isinstance(preferences, dict) and preferences.get("parking"))
    plot_facing_direction = str(parsed_input.get("plot_facing_direction", "north"))

    # ── Vertical cores: lock footprints on Floor 0 ────────────────
    fixed_cores = _build_fixed_cores(slots)
    notes.append(
        f"Vertical cores locked: stair_core {fixed_cores['stair_core']}, "
        f"service_shaft {fixed_cores['service_shaft']}."
    )

    # Remove any existing 'staircase' entries from the room queue
    # because vertical cores replace the generic staircase slot.
    room_queue = [r for r in room_queue if r != "staircase"]

    for floor in range(floors):
        # ── 1. Emit fixed vertical cores for every floor ──────────
        for core_type, core_fp in fixed_cores.items():
            zone_counter += 1
            zones.append({
                "id": f"zone_{zone_counter}",
                "room_type": core_type,
                "floor": floor,
                "slot_index": -1,  # Not a regular quadrant slot
                "x": core_fp["x"],
                "y": core_fp["y"],
                "width_m": core_fp["width_m"],
                "depth_m": core_fp["depth_m"],
                "orientation": "core",
                "is_fixed": True,
            })

        # ── 2. Build floor program (minus staircase, now a core) ──
        floor_rooms = _build_floor_program(
            room_queue=room_queue,
            floor=floor,
            slot_capacity=len(slots),
            parking_requested=parking_requested,
        )
        # Drop any staircase that _build_floor_program force-inserted;
        # it's already covered by stair_core above.
        floor_rooms = [r for r in floor_rooms if r != "staircase"]

        # Pad back to slot_capacity with circulation if we removed entries.
        while len(floor_rooms) < len(slots):
            floor_rooms.append("circulation")

        assigned_by_slot = _assign_rooms_to_slots(
            floor_rooms=floor_rooms,
            slots=slots,
            floor=floor,
            plot_facing_direction=plot_facing_direction,
        )

        for slot_index, slot in enumerate(slots):
            room = assigned_by_slot.get(slot_index, "multi_use")
            zone_counter += 1
            zones.append(
                {
                    "id": f"zone_{zone_counter}",
                    "room_type": room,
                    "floor": floor,
                    "slot_index": slot_index,
                    "x": round(slot["x"], 3),
                    "y": round(slot["y"], 3),
                    "width_m": round(slot["width_m"], 3),
                    "depth_m": round(slot["depth_m"], 3),
                    "orientation": slot["orientation"],
                    "is_fixed": False,
                }
            )

    if room_queue:
        notes.append(
            f"{len(room_queue)} requested room entries were not explicitly allocated and should be refined interactively."
        )

    # ── Corridor width check ──────────────────────────────────────
    corridor_check = check_corridor_widths(zones)
    if not corridor_check["passed"]:
        notes.append(
            f"Corridor width check failed: {len(corridor_check['issues'])} corridor(s) "
            f"narrower than {MIN_CORRIDOR_WIDTH_M}m."
        )

    layout_metrics = _compute_layout_metrics(zones)
    layout_metrics["corridor_check"] = corridor_check
    notes.append(
        f"Overall layout quality score: {layout_metrics['overall_layout_quality_score']}/100."
    )
    for floor_metric in layout_metrics["floor_metrics"]:
        notes.append(
            "Floor "
            f"{floor_metric['floor']} score: {floor_metric['layout_quality_score']}/100 "
            f"(adjacency {floor_metric['adjacency_score']}, "
            f"circulation {floor_metric['circulation_score']})."
        )
        if floor_metric["unmet_adjacencies"]:
            notes.append(
                f"Floor {floor_metric['floor']} unmet adjacencies: "
                + ", ".join(sorted(floor_metric["unmet_adjacencies"]))
            )

    return {
        "zones": zones,
        "layout_notes": notes,
        "footprint": footprint,
        "layout_metrics": layout_metrics,
    }
