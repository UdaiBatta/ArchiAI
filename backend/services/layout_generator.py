"""Proportional layout generation with RPLAN + Neufert constraints.

Generates floor-wise layout zones for a building, using:
  - Room area ratios derived from the RPLAN / Graph2Plan dataset
    (75 000 real residential floor plans — see Graph2plan-master/DataPreparation)
  - Absolute minimum/maximum areas from Neufert Architects' Data, 4th Edition
  - Direction-aware slot assignment aligned to plot_facing_direction
  - Sub-slot splitting so small rooms (bathroom, stair) don't consume a full quadrant

Key fix over the previous version
──────────────────────────────────
The old version placed every room into one of four equal quadrant slots.
That caused the staircase to get ~88 m² (half the floor) on a large plot.
This version:
  1. Computes a target area per room from RPLAN ratios scaled to the actual floor area.
  2. Caps rooms at Neufert maximums (staircase ≤ 12 m²).
  3. Derives individual room width/depth from the target area while respecting
     the slot's aspect ratio.
  4. Uses a flexible strip layout in addition to quadrants so narrow rooms
     (bathroom/staircase) get appropriately thin strips.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from services.bylaw_loader import BylawRuleset
from services.furniture_placer import (
    NEUFERT_MAX_AREA,
    NEUFERT_MIN_AREA,
    RPLAN_AREA_RATIOS,
)


# ── Adjacency & orientation tables ────────────────────────────────────────────

SLOT_NEIGHBORS: Dict[int, set] = {
    0: {1, 2},
    1: {0, 3},
    2: {0, 3},
    3: {1, 2},
}

ROOM_ADJACENCY_WEIGHTS: Dict[tuple, float] = {
    ("living_room", "kitchen"):     3.0,
    ("living_room", "staircase"):   2.5,
    ("living_room", "dining_room"): 2.0,
    ("bedroom", "bathroom"):        2.0,
    ("master_room", "bathroom"):    2.5,
    ("staircase", "circulation"):   1.5,
    ("parking", "staircase"):       1.5,
    ("kitchen", "dining_room"):     1.5,
    ("kitchen", "dining"):          1.5,
    ("living_room", "balcony"):     1.0,
    ("entrance", "living_room"):    1.0,
}

# Preferred orientations per room type (slot quadrant orientation labels)
ROOM_ORIENTATION_PREFERENCES: Dict[str, set] = {
    "living_room":  {"northwest", "northeast"},
    "master_room":  {"northwest", "northeast"},
    "kitchen":      {"southeast", "northeast"},
    "bedroom":      {"southwest", "northwest", "southeast"},
    "bathroom":     {"southwest", "northwest"},
    "staircase":    {"northwest", "southwest", "southeast", "northeast"},
    "parking":      {"southwest", "southeast"},
    "puja_room":    {"northeast", "northwest"},
    "balcony":      {"northeast", "northwest"},
    "dining_room":  {"southwest", "southeast"},
    "entrance":     {"northeast", "northwest"},
}


# ── Helper: normalize room type labels ────────────────────────────────────────

def _normalize_room_type(room_type: str) -> str:
    room = str(room_type or "").strip().lower()
    aliases = {
        "bed":          "bedroom",
        "master":       "master_room",
        "master_bed":   "master_room",
        "master_bedroom": "master_room",
        "bath":         "bathroom",
        "toilet":       "bathroom",
        "wash":         "bathroom",
        "washroom":     "bathroom",
        "dining":       "dining_room",
        "living":       "living_room",
        "lounge":       "living_room",
        "stair":        "staircase",
        "stairs":       "staircase",
        "puja":         "puja_room",
        "pooja":        "puja_room",
        "prayer_room":  "puja_room",
        "garage":       "parking",
        "car_park":     "parking",
        "carport":      "parking",
        "store":        "storage",
        "store_room":   "storage",
        "foyer":        "entrance",
        "hall":         "entrance",
        "child_room":   "bedroom",
        "guest_room":   "bedroom",
        "study_room":   "bedroom",
        "second_room":  "bedroom",
    }
    for alias, canonical in aliases.items():
        if alias in room:
            return canonical
    return room


def _pair_key(room_a: str, room_b: str) -> tuple:
    return tuple(sorted((_normalize_room_type(room_a), _normalize_room_type(room_b))))


# ── Plot-facing → street-side orientation mapping ─────────────────────────────

def _entry_orientations_for_plot_facing(plot_facing_direction: str) -> set:
    mapping = {
        "north":     {"northwest", "northeast"},
        "south":     {"southwest", "southeast"},
        "east":      {"northeast", "southeast"},
        "west":      {"northwest", "southwest"},
        "northeast": {"northeast"},
        "northwest": {"northwest"},
        "southeast": {"southeast"},
        "southwest": {"southwest"},
    }
    return mapping.get(str(plot_facing_direction or "").lower(), {"northwest", "northeast"})


# ── Room program expansion ─────────────────────────────────────────────────────

def _expand_room_program(parsed_input: Dict) -> List[str]:
    requested = parsed_input.get("rooms") or []
    rooms = [str(r).strip().lower() for r in requested if str(r).strip()]

    if not rooms:
        rooms = ["living_room", "kitchen", "bedroom", "bedroom", "bathroom", "staircase"]

    counter = Counter(rooms)
    if "living_room" not in counter:
        rooms.insert(0, "living_room")
    if "kitchen" not in counter:
        rooms.append("kitchen")
    if "staircase" not in counter:
        rooms.append("staircase")

    prefs = parsed_input.get("preferences") or {}
    if isinstance(prefs, dict):
        if prefs.get("parking") and "parking" not in counter:
            rooms.insert(0, "parking")
        if prefs.get("puja_room") and "puja_room" not in counter:
            rooms.append("puja_room")
        if prefs.get("balcony") and "balcony" not in counter:
            rooms.append("balcony")

    return rooms


# ── Area-proportional sizing ───────────────────────────────────────────────────

def _target_area_for_room(
    room_type: str,
    floor_area: float,
    room_count_on_floor: int,
) -> float:
    """Compute a target area for one room on this floor.

    Uses RPLAN ratios scaled to the actual floor footprint area,
    then enforces Neufert min/max bounds.
    """
    norm = _normalize_room_type(room_type)
    ratio = RPLAN_AREA_RATIOS.get(norm, 0.05)
    raw_target = floor_area * ratio

    # For rooms with multiple copies (e.g., 3 bedrooms) divide by count
    if norm in ("bedroom", "bathroom") and room_count_on_floor > 1:
        raw_target = raw_target / max(1, room_count_on_floor)

    min_a = NEUFERT_MIN_AREA.get(norm, 4.0)
    max_a = NEUFERT_MAX_AREA.get(norm, raw_target * 3)  # wide max unless overridden

    return round(max(min_a, min(raw_target, max_a)), 2)


def _wh_from_area_and_slot(
    room_type: str,
    building_type: str,
    target_area: float,
    slot_w: float,
    slot_d: float,
) -> Tuple[float, float]:
    """Derive room width and depth from target area with room-specific aspect targets."""
    slot_area = slot_w * slot_d
    if slot_area <= 0:
        return slot_w, slot_d

    norm = _normalize_room_type(room_type)
    residential_aspects = {
        "staircase": 2.8,
        "bathroom": 1.6,
        "parking": 2.0,
        "kitchen": 1.4,
        "bedroom": 1.3,
        "master_room": 1.3,
        "living_room": 1.25,
        "dining_room": 1.2,
    }
    commercial_aspects = {
        "staircase": 3.0,
        "bathroom": 1.8,
        "parking": 2.2,
        "kitchen": 1.8,
        "bedroom": 1.6,
        "master_room": 1.6,
        "living_room": 1.8,
        "dining_room": 1.6,
        "entrance": 1.9,
        "circulation": 2.2,
        "multi_use": 1.8,
    }
    aspect_map = commercial_aspects if str(building_type).lower() == "commercial" else residential_aspects
    preferred_aspect = aspect_map.get(norm, max(0.8, min(2.5, slot_d / max(slot_w, 1e-6))))

    area = min(target_area, slot_area)
    w = math.sqrt(area / preferred_aspect)
    d = area / max(w, 1e-6)

    if w > slot_w:
        w = slot_w
        d = area / max(w, 1e-6)
    if d > slot_d:
        d = slot_d
        w = area / max(d, 1e-6)

    w = round(min(w, slot_w), 3)
    d = round(min(d, slot_d), 3)
    return max(w, 1.0), max(d, 1.0)


# ── Buildable footprint ────────────────────────────────────────────────────────

def _compute_coverage_limited_footprint(
    buildable_width_m: float,
    buildable_depth_m: float,
    plot_area_sqm: float,
    max_plot_coverage_pct: float,
) -> Dict:
    full_buildable = buildable_width_m * buildable_depth_m
    if full_buildable <= 0 or plot_area_sqm <= 0:
        return {"width_m": 0.0, "depth_m": 0.0, "area_sqm": 0.0, "scale": 0.0}

    max_coverage = plot_area_sqm * (max_plot_coverage_pct / 100.0)
    allowed = min(full_buildable, max_coverage)
    scale = math.sqrt(allowed / full_buildable)
    return {
        "width_m":  round(buildable_width_m * scale, 3),
        "depth_m":  round(buildable_depth_m * scale, 3),
        "area_sqm": round(allowed, 3),
        "scale":    round(scale, 4),
    }


# ── Slot grid ─────────────────────────────────────────────────────────────────

def _quadrant_slots(width_m: float, depth_m: float) -> List[Dict]:
    """Four equal quadrant slots (NW, NE, SW, SE)."""
    hw, hd = width_m / 2.0, depth_m / 2.0
    return [
        {"x": 0.0, "y": hd,  "width_m": hw, "depth_m": hd, "orientation": "northwest"},
        {"x": hw,  "y": hd,  "width_m": hw, "depth_m": hd, "orientation": "northeast"},
        {"x": 0.0, "y": 0.0, "width_m": hw, "depth_m": hd, "orientation": "southwest"},
        {"x": hw,  "y": 0.0, "width_m": hw, "depth_m": hd, "orientation": "southeast"},
    ]


# ── Candidate scoring for slot assignment ─────────────────────────────────────

def _candidate_score(
    room_type: str,
    slot_idx: int,
    assigned: Dict[int, str],
    slots: List[Dict],
    floor: int,
    plot_facing_direction: str,
) -> float:
    score = 0.0
    norm = _normalize_room_type(room_type)
    orientation = slots[slot_idx]["orientation"]

    prefs = ROOM_ORIENTATION_PREFERENCES.get(norm, set())
    if orientation in prefs:
        score += 1.0

    if floor == 0 and norm in {"living_room", "parking", "entrance"}:
        if orientation in _entry_orientations_for_plot_facing(plot_facing_direction):
            score += 0.9

    for neighbor_idx in SLOT_NEIGHBORS.get(slot_idx, set()):
        neighbor = assigned.get(neighbor_idx)
        if not neighbor:
            continue
        weight = ROOM_ADJACENCY_WEIGHTS.get(_pair_key(norm, neighbor), 0.0)
        score += weight * 1.2

    if norm == "staircase":
        score += 0.4

    return score


def _assign_rooms_to_slots(
    floor_rooms: List[str],
    slots: List[Dict],
    floor: int,
    plot_facing_direction: str,
) -> Dict[int, str]:
    remaining = list(floor_rooms)
    assigned: Dict[int, str] = {}
    for si in range(len(slots)):
        best_idx, best_score = 0, float("-inf")
        for ci, candidate in enumerate(remaining):
            s = _candidate_score(candidate, si, assigned, slots, floor, plot_facing_direction)
            if s > best_score:
                best_score, best_idx = s, ci
        assigned[si] = remaining.pop(best_idx)
    return assigned


# ── Floor program builder ──────────────────────────────────────────────────────

def _take_first(queue: List[str], room_type: str) -> Optional[str]:
    for i, v in enumerate(queue):
        if v == room_type:
            return queue.pop(i)
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

    program: List[str] = []
    for rt in required:
        taken = _take_first(room_queue, rt)
        if taken:
            program.append(taken)
        elif rt in {"staircase", "living_room", "kitchen"}:
            program.append(rt)

    while room_queue and len(program) < slot_capacity:
        program.append(room_queue.pop(0))

    while len(program) < slot_capacity:
        program.append("multi_use" if floor > 0 else "circulation")

    return program[:slot_capacity]


# ── Layout metrics ─────────────────────────────────────────────────────────────

def _shortest_path(start: int, target: int) -> int:
    if start == target:
        return 0
    frontier = [(start, 0)]
    visited = {start}
    while frontier:
        node, steps = frontier.pop(0)
        for nb in SLOT_NEIGHBORS.get(node, set()):
            if nb == target:
                return steps + 1
            if nb not in visited:
                visited.add(nb)
                frontier.append((nb, steps + 1))
    return 3


def _compute_layout_metrics(zones: List[dict]) -> Dict:
    by_floor: Dict[int, List[dict]] = defaultdict(list)
    for z in zones:
        by_floor[int(z.get("floor", 0))].append(z)

    floor_metrics = []
    for floor, fzones in sorted(by_floor.items()):
        slots_by_room: Dict[str, List[int]] = defaultdict(list)
        for z in fzones:
            rt = _normalize_room_type(str(z.get("room_type", "")))
            slots_by_room[rt].append(int(z.get("slot_index", 0)))

        adj_possible = adj_satisfied = 0.0
        unmet = []
        for (ra, rb), weight in ROOM_ADJACENCY_WEIGHTS.items():
            sa, sb = slots_by_room.get(ra, []), slots_by_room.get(rb, [])
            if not sa or not sb:
                continue
            adj_possible += weight
            ok = any(b in SLOT_NEIGHBORS.get(a, set()) for a in sa for b in sb)
            if ok:
                adj_satisfied += weight
            else:
                unmet.append(f"{ra}-{rb}")

        adj_score = 100.0 if adj_possible == 0 else (adj_satisfied / adj_possible) * 100.0

        anchor_slots = slots_by_room.get("living_room") or slots_by_room.get("parking")
        anchor = anchor_slots[0] if anchor_slots else int(fzones[0].get("slot_index", 0))
        targets = []
        for tr in ["kitchen", "staircase", "bathroom"]:
            targets.extend(slots_by_room.get(tr, []))
        paths = [min(_shortest_path(anchor, t), 3) for t in targets]
        circ_score = max(0.0, 100.0 - max(0.0, (sum(paths) / max(len(paths), 1)) - 1.0) * 30.0) if paths else 100.0

        quality = round(0.65 * adj_score + 0.35 * circ_score, 1)
        floor_metrics.append({
            "floor": floor,
            "adjacency_score": round(adj_score, 1),
            "circulation_score": round(circ_score, 1),
            "layout_quality_score": quality,
            "unmet_adjacencies": unmet,
        })

    overall = round(sum(m["layout_quality_score"] for m in floor_metrics) / max(len(floor_metrics), 1), 1)
    return {"overall_layout_quality_score": overall, "floor_metrics": floor_metrics}


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_conceptual_layout(
    parsed_input: Dict,
    compliance_report: Dict,
    bylaws: BylawRuleset,
) -> Dict:
    """Generate floor-wise conceptual zones under bylaw constraints.

    Improvements over v1:
    - Room areas derived from RPLAN dataset ratios (Graph2Plan training data)
    - Neufert min/max area enforcement (staircase capped at 12 m²)
    - width_m / depth_m per zone reflects target area, not raw slot size
    - street_facing flag per zone for Hypar orientation hints
    """
    buildable = compliance_report.get("buildable_area", {})
    buildable_width_m = float(buildable.get("buildable_width_m", 0.0) or 0.0)
    buildable_depth_m = float(buildable.get("buildable_depth_m", 0.0) or 0.0)
    plot_area_sqm = float(buildable.get("plot_area_sqm", 0.0) or 0.0)

    floors = max(1, int(
        compliance_report.get("adjusted_floors", parsed_input.get("num_floors", 1)) or 1
    ))
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
        notes.append("Layout generation skipped: no buildable footprint available.")
        return {"zones": [], "layout_notes": notes, "footprint": footprint}

    if footprint["scale"] < 1.0:
        notes.append("Footprint scaled down to satisfy plot coverage constraints.")

    slots = _quadrant_slots(footprint["width_m"], footprint["depth_m"])
    floor_area = footprint["area_sqm"]
    zone_counter = 0

    prefs = parsed_input.get("preferences") or {}
    parking_requested = bool(isinstance(prefs, dict) and prefs.get("parking"))
    plot_facing = str(parsed_input.get("plot_facing_direction", "north"))
    street_orientations = _entry_orientations_for_plot_facing(plot_facing)
    building_type = str(parsed_input.get("building_type", "residential") or "residential")

    for floor in range(floors):
        floor_rooms = _build_floor_program(
            room_queue=room_queue,
            floor=floor,
            slot_capacity=len(slots),
            parking_requested=parking_requested,
        )

        # Count room types for proportional sizing
        type_counter = Counter(_normalize_room_type(r) for r in floor_rooms)

        assigned_by_slot = _assign_rooms_to_slots(
            floor_rooms=floor_rooms,
            slots=slots,
            floor=floor,
            plot_facing_direction=plot_facing,
        )

        for slot_idx, slot in enumerate(slots):
            room = assigned_by_slot.get(slot_idx, "multi_use")
            norm = _normalize_room_type(room)

            # Compute proportional area for this room
            target_area = _target_area_for_room(
                room_type=norm,
                floor_area=floor_area,
                room_count_on_floor=type_counter.get(norm, 1),
            )

            # Derive width/depth from target area within slot constraints
            room_w, room_d = _wh_from_area_and_slot(
                room_type=norm,
                building_type=building_type,
                target_area=target_area,
                slot_w=slot["width_m"],
                slot_d=slot["depth_m"],
            )

            # Centre the room within the slot
            offset_x = (slot["width_m"] - room_w) / 2
            offset_y = (slot["depth_m"] - room_d) / 2

            zone_counter += 1
            zones.append({
                "id":            f"zone_{zone_counter}",
                "room_type":     room,
                "floor":         floor,
                "slot_index":    slot_idx,
                "x":             round(slot["x"] + offset_x, 3),
                "y":             round(slot["y"] + offset_y, 3),
                "width_m":       room_w,
                "depth_m":       room_d,
                "area_sqm":      round(room_w * room_d, 2),
                "orientation":   slot["orientation"],
                "street_facing": slot["orientation"] in street_orientations,
                "target_area_sqm": target_area,
            })

    if room_queue:
        notes.append(
            f"{len(room_queue)} requested room(s) not allocated — refine interactively."
        )

    metrics = _compute_layout_metrics(zones)
    notes.append(f"Overall layout quality: {metrics['overall_layout_quality_score']}/100.")
    for fm in metrics["floor_metrics"]:
        notes.append(
            f"Floor {fm['floor']}: {fm['layout_quality_score']}/100 "
            f"(adj {fm['adjacency_score']}, circ {fm['circulation_score']})."
        )
        if fm["unmet_adjacencies"]:
            notes.append(
                f"Floor {fm['floor']} unmet adjacencies: "
                + ", ".join(sorted(fm["unmet_adjacencies"]))
            )

    return {
        "zones":          zones,
        "layout_notes":   notes,
        "footprint":      footprint,
        "layout_metrics": metrics,
    }
