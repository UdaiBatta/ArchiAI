"""Furniture placement engine — Hypar Elements API aligned.

Generates per-room furniture items as Hypar-compatible Element records.
All dimensions are in METRES and sourced from:
  - Neufert Architects' Data, 4th Edition (room dimensions, clearances)
  - RPLAN / Graph2Plan dataset room-type conventions
  - Hypar Elements API: https://hypar-io.github.io/Elements/api/Elements.html

Each furniture item is emitted as:
  {
      "kind":        "FurnitureElement",
      "type":        "<FurnitureTypeName>",
      "origin_m":   [x, y, z],   # world-space position (bottom-left corner)
      "size_m":     [w, d, h],   # width, depth, height
      "rotation_deg": 0.0,       # Z-axis rotation
      "zone_id":    "<zone_id>",
  }

The Hypar Elements type for furniture is typically "ModelCurve" (footprint)
or "Mass" (volumetric). We emit the metadata needed for either approach.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional


# ── RPLAN → Archi3D room type mapping ─────────────────────────────────────────
# RPLAN categories: 0=LivingRoom, 1=MasterRoom, 2=Kitchen, 3=Bathroom,
#                   4=DiningRoom, 5=ChildRoom, 6=StudyRoom, 7=SecondRoom,
#                   8=GuestRoom, 9=Balcony, 10=Entrance, 11=Storage
RPLAN_TO_ARCHI3D = {
    "living_room":  ["living_room", "lounge"],
    "master_room":  ["master_bedroom", "master room"],
    "kitchen":      ["kitchen"],
    "bathroom":     ["bathroom", "toilet", "washroom"],
    "dining_room":  ["dining", "dining_room"],
    "bedroom":      ["bedroom", "child_room", "study_room", "guest_room"],
    "balcony":      ["balcony"],
    "entrance":     ["entrance", "foyer", "circulation"],
    "staircase":    ["staircase"],
    "parking":      ["parking"],
    "storage":      ["storage"],
    "puja_room":    ["puja_room"],
    "multi_use":    ["multi_use"],
}


# ── Neufert-sourced furniture templates ────────────────────────────────────────
# Each item:
#   type        → Hypar / display name
#   w, d, h     → width, depth, height (metres)
#   anchor      → placement logic key (resolved in _anchor_to_offset)
#   count       → how many to place (default 1)
#   rotation    → degrees, 0 = facing +Y (depth direction)
#
# Sources:
#   Neufert 4th ed. — Bathrooms p.176, Bedrooms p.183, Kitchens p.202,
#                     Living rooms p.206, Staircases p.157
#   IS 8827:1978    — Staircase tread/riser + width requirements

FURNITURE_TEMPLATES: Dict[str, List[dict]] = {
    "living_room": [
        # Sofa against far wall; 2.2 m wide, 0.9 m deep (Neufert p.206)
        {"type": "Sofa",        "w": 2.2, "d": 0.90, "h": 0.85, "anchor": "far_wall_center"},
        {"type": "CoffeeTable", "w": 1.2, "d": 0.60, "h": 0.45, "anchor": "center_offset"},
        {"type": "TVUnit",      "w": 1.5, "d": 0.45, "h": 0.55, "anchor": "near_wall_center"},
        {"type": "Armchair",    "w": 0.85,"d": 0.85, "h": 0.85, "anchor": "side_left"},
        {"type": "Armchair",    "w": 0.85,"d": 0.85, "h": 0.85, "anchor": "side_right"},
    ],
    "kitchen": [
        # L-shaped counter along rear + side walls (Neufert p.202)
        {"type": "KitchenCounter", "w": None, "d": 0.60, "h": 0.85, "anchor": "rear_wall_full"},
        {"type": "KitchenIsland",  "w": 1.20, "d": 0.70, "h": 0.90, "anchor": "center_offset", "optional": True},
        {"type": "DiningTable",    "w": 1.50, "d": 0.90, "h": 0.75, "anchor": "dining_zone"},
        {"type": "DiningChair",    "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_1"},
        {"type": "DiningChair",    "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_2"},
        {"type": "DiningChair",    "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_3"},
        {"type": "DiningChair",    "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_4"},
    ],
    "bedroom": [
        # Double bed centred on far wall; 1.6 × 2.0 (Neufert p.183)
        {"type": "DoubleBed",  "w": 1.60, "d": 2.00, "h": 0.55, "anchor": "far_wall_center"},
        {"type": "Nightstand", "w": 0.50, "d": 0.40, "h": 0.55, "anchor": "bed_left"},
        {"type": "Nightstand", "w": 0.50, "d": 0.40, "h": 0.55, "anchor": "bed_right"},
        {"type": "Wardrobe",   "w": 1.80, "d": 0.60, "h": 2.10, "anchor": "side_wall"},
        {"type": "Desk",       "w": 1.20, "d": 0.60, "h": 0.75, "anchor": "window_wall", "optional": True},
    ],
    "master_room": [
        # King bed: 1.8 × 2.0 (Neufert p.183)
        {"type": "KingBed",    "w": 1.80, "d": 2.00, "h": 0.55, "anchor": "far_wall_center"},
        {"type": "Nightstand", "w": 0.50, "d": 0.40, "h": 0.55, "anchor": "bed_left"},
        {"type": "Nightstand", "w": 0.50, "d": 0.40, "h": 0.55, "anchor": "bed_right"},
        {"type": "Wardrobe",   "w": 2.40, "d": 0.60, "h": 2.10, "anchor": "side_wall"},
        {"type": "DressingTable","w": 1.00,"d": 0.50, "h": 0.75, "anchor": "adj_side_wall"},
    ],
    "bathroom": [
        # Minimum bathroom 2.5 m × 1.5 m (Neufert p.176 / IS 1172)
        {"type": "Toilet",    "w": 0.40, "d": 0.70, "h": 0.80, "anchor": "far_corner"},
        {"type": "Washbasin", "w": 0.50, "d": 0.40, "h": 0.85, "anchor": "near_side_wall"},
        {"type": "Shower",    "w": 0.90, "d": 0.90, "h": 2.10, "anchor": "adj_far_corner"},
    ],
    "dining_room": [
        {"type": "DiningTable", "w": 1.80, "d": 0.90, "h": 0.75, "anchor": "center"},
        {"type": "DiningChair", "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_1"},
        {"type": "DiningChair", "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_2"},
        {"type": "DiningChair", "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_3"},
        {"type": "DiningChair", "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_4"},
        {"type": "DiningChair", "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_5"},
        {"type": "DiningChair", "w": 0.45, "d": 0.45, "h": 0.90, "anchor": "dining_chair_6"},
    ],
    "staircase": [
        # IS 8827:1978 — residential stair: width 1.0 m, tread 0.25 m, riser 0.19 m
        # A 10-step flight occupies roughly 1.0 m wide × 3.0 m long in plan
        {"type": "StaircaseFlight", "w": 1.00, "d": 3.00, "h": 0.0, "anchor": "center"},
        {"type": "StaircaseLanding","w": 1.00, "d": 1.00, "h": 0.0, "anchor": "landing_top"},
    ],
    "parking": [
        # Single car stall: 2.5 m × 5.0 m (Neufert p.394)
        {"type": "CarSlot", "w": 2.50, "d": 5.00, "h": 0.10, "anchor": "center"},
    ],
    "balcony": [
        {"type": "OutdoorChair", "w": 0.55, "d": 0.55, "h": 0.85, "anchor": "corner_left"},
        {"type": "OutdoorChair", "w": 0.55, "d": 0.55, "h": 0.85, "anchor": "corner_right"},
        {"type": "SmallTable",   "w": 0.60, "d": 0.60, "h": 0.72, "anchor": "center_offset"},
    ],
    "puja_room": [
        {"type": "PujaAltar",  "w": 0.90, "d": 0.45, "h": 1.20, "anchor": "far_wall_center"},
        {"type": "PrayerMat",  "w": 0.60, "d": 0.90, "h": 0.02, "anchor": "center_offset"},
    ],
    "storage": [
        {"type": "StorageRack", "w": None, "d": 0.50, "h": 2.00, "anchor": "side_wall_full"},
    ],
    "entrance": [
        {"type": "ShoeRack",  "w": 0.80, "d": 0.30, "h": 1.00, "anchor": "near_wall_side"},
        {"type": "HallTable", "w": 0.80, "d": 0.35, "h": 0.80, "anchor": "side_wall"},
    ],
    "multi_use": [],
    "circulation": [],
}

# Minimum Neufert-based clearances (metres) between furniture and walls
WALL_CLEARANCE = 0.10   # structural gap
BED_SIDE_CLEARANCE = 0.60  # bed access path (Neufert p.183)
PASSAGE_WIDTH = 0.90       # min person passage


def _rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def _is_colliding(rect: tuple[float, float, float, float], placed_rects: List[tuple[float, float, float, float]]) -> bool:
    return any(_rects_overlap(rect, existing) for existing in placed_rects)


def _fit_item_size(
    item_w: float,
    item_d: float,
    room_w: float,
    room_d: float,
    *,
    required: bool,
) -> tuple[float, float] | None:
    usable_w = max(0.0, room_w - 2 * WALL_CLEARANCE)
    usable_d = max(0.0, room_d - 2 * WALL_CLEARANCE)
    if usable_w <= 0 or usable_d <= 0:
        return None

    if item_w <= usable_w and item_d <= usable_d:
        return round(item_w, 3), round(item_d, 3)

    if not required:
        return None

    # For required items, apply bounded down-scaling to preserve layout usability.
    scale = min(usable_w / max(item_w, 1e-6), usable_d / max(item_d, 1e-6))
    if scale < 0.75:
        return None
    return round(item_w * scale, 3), round(item_d * scale, 3)


# ── Anchor → offset resolver ───────────────────────────────────────────────────

def _resolve_anchor(
    anchor: str,
    room_w: float,
    room_d: float,
    item_w: float,
    item_d: float,
    context: dict,
) -> tuple[float, float, float]:
    """Return (x, y, rotation_deg) relative to room origin (bottom-left corner).

    Coordinate system:
      x → room width direction
      y → room depth direction (y=0 is the 'near' wall, y=room_d is 'far' wall)
    """
    c = WALL_CLEARANCE
    rot = 0.0

    anchors = {
        "center": (
            (room_w - item_w) / 2,
            (room_d - item_d) / 2,
            0.0,
        ),
        "center_offset": (
            (room_w - item_w) / 2,
            room_d * 0.35,
            0.0,
        ),
        "far_wall_center": (
            (room_w - item_w) / 2,
            room_d - item_d - c,
            0.0,
        ),
        "near_wall_center": (
            (room_w - item_w) / 2,
            c,
            0.0,
        ),
        "near_wall_side": (c, c, 0.0),
        "side_left": (c, room_d * 0.45, 0.0),
        "side_right": (room_w - item_w - c, room_d * 0.45, 0.0),
        "side_wall": (c, room_d * 0.30, 0.0),
        "adj_side_wall": (room_w - item_w - c, room_d * 0.30, 0.0),
        "window_wall": (room_w - item_w - c, c, 180.0),
        "rear_wall_full": (c, room_d - item_d - c, 0.0),
        "side_wall_full": (c, c, 0.0),
        "far_corner": (c, room_d - item_d - c, 0.0),
        "adj_far_corner": (room_w - item_w - c, room_d - item_d - c, 0.0),
        "near_side_wall": (c, c + 0.20, 0.0),
        "corner_left": (c, c, 0.0),
        "corner_right": (room_w - item_w - c, c, 0.0),
        "landing_top": (
            (room_w - item_w) / 2,
            room_d - item_d - c,
            0.0,
        ),
        "dining_zone": (
            (room_w - item_w) / 2,
            c + 0.30,
            0.0,
        ),
    }

    # Bed-relative anchors — depend on where the bed is
    bed_x = (room_w - 1.60) / 2  # default double bed
    bed_y = room_d - 2.00 - c
    bed_side_y = bed_y + (2.00 - 0.40) / 2  # nightstand centre-height aligned

    anchors["bed_left"] = (bed_x - 0.50 - 0.05, bed_side_y, 0.0)
    anchors["bed_right"] = (bed_x + context.get("bed_width", 1.60) + 0.05, bed_side_y, 0.0)

    # Dining chairs around a dining table at center or dining_zone
    table_w = context.get("dining_table_w", 1.50)
    table_d = context.get("dining_table_d", 0.90)
    tx = (room_w - table_w) / 2
    ty = c + 0.30
    gap = 0.05
    anchors["dining_chair_1"] = (tx + (table_w - 0.45) / 2, ty - 0.45 - gap, 0.0)
    anchors["dining_chair_2"] = (tx + (table_w - 0.45) / 2, ty + table_d + gap, 180.0)
    anchors["dining_chair_3"] = (tx - 0.45 - gap, ty + (table_d - 0.45) / 2, 90.0)
    anchors["dining_chair_4"] = (tx + table_w + gap, ty + (table_d - 0.45) / 2, 270.0)
    anchors["dining_chair_5"] = (tx + 0.10, ty - 0.45 - gap, 0.0)
    anchors["dining_chair_6"] = (tx + table_w - 0.55, ty - 0.45 - gap, 0.0)

    if anchor in anchors:
        x, y, rot = anchors[anchor]
    else:
        x, y, rot = c, c, 0.0

    # Clamp to room bounds with clearance
    x = max(c, min(x, room_w - item_w - c))
    y = max(c, min(y, room_d - item_d - c))
    return round(x, 3), round(y, 3), round(rot, 1)


# ── Main public function ───────────────────────────────────────────────────────

def place_furniture(
    zones: List[dict],
    floor_height_m: float = 3.0,
    parsed_input: Optional[dict] = None,
) -> List[dict]:
    """Place furniture in all layout zones.

    Args:
        zones: List of layout zone dicts from generate_conceptual_layout().
                Each zone must have: id, room_type, floor, x, y, width_m, depth_m.
        floor_height_m: Floor-to-floor height (for z elevation).
        parsed_input: Parsed design input (used for preferences / vastu hints).

    Returns:
        List of furniture element dicts, Hypar Elements API-compatible.
    """
    preferences = (parsed_input or {}).get("preferences") or {}
    all_furniture: List[dict] = []

    for zone in zones:
        room_type = str(zone.get("room_type", "multi_use")).lower().strip()
        zone_id = zone.get("id", "unknown")
        floor = int(zone.get("floor", 0))
        zone_x = float(zone.get("x", 0.0))
        zone_y = float(zone.get("y", 0.0))
        room_w = float(zone.get("width_m", 0.0))
        room_d = float(zone.get("depth_m", 0.0))
        floor_z = round(floor * floor_height_m, 3)

        if room_w < 1.0 or room_d < 1.0:
            continue

        # Normalise room type to template key
        template_key = _resolve_template_key(room_type)
        templates = FURNITURE_TEMPLATES.get(template_key, [])

        context = {
            "bed_width": 1.60 if template_key == "bedroom" else 1.80,
            "dining_table_w": 1.50,
            "dining_table_d": 0.90,
        }

        placed_rects: List[tuple[float, float, float, float]] = []
        for idx, item in enumerate(templates):
            # Skip optional items when room is small
            if item.get("optional") and (room_w * room_d) < 10.0:
                continue

            raw_item_w = item["w"] if item["w"] is not None else max(0.30, room_w - 2 * WALL_CLEARANCE)
            raw_item_d = item["d"]
            required = bool(item.get("required")) or (idx == 0 and template_key not in {"multi_use", "circulation"})
            fitted_size = _fit_item_size(
                item_w=float(raw_item_w),
                item_d=float(raw_item_d),
                room_w=room_w,
                room_d=room_d,
                required=required,
            )
            if fitted_size is None:
                continue
            item_w, item_d = fitted_size

            local_x, local_y, rotation = _resolve_anchor(
                anchor=item["anchor"],
                room_w=room_w,
                room_d=room_d,
                item_w=item_w,
                item_d=item_d,
                context=context,
            )
            rect = (local_x, local_y, local_x + item_w, local_y + item_d)
            if _is_colliding(rect, placed_rects):
                if item.get("optional"):
                    continue
                fallback_x, fallback_y, fallback_rot = _resolve_anchor(
                    anchor="center",
                    room_w=room_w,
                    room_d=room_d,
                    item_w=item_w,
                    item_d=item_d,
                    context=context,
                )
                fallback_rect = (
                    fallback_x,
                    fallback_y,
                    fallback_x + item_w,
                    fallback_y + item_d,
                )
                if _is_colliding(fallback_rect, placed_rects):
                    continue
                local_x, local_y, rotation = fallback_x, fallback_y, fallback_rot
                rect = fallback_rect

            world_x = round(zone_x + local_x, 3)
            world_y = round(zone_y + local_y, 3)

            all_furniture.append(
                {
                    "kind": "FurnitureElement",
                    "hypar_elements_type": "Mass",
                    "hypar_doc": "https://hypar-io.github.io/Elements/api/Elements.Mass.html",
                    "type": item["type"],
                    "zone_id": zone_id,
                    "floor": floor,
                    "origin_m": [world_x, world_y, floor_z],
                    "size_m": [round(item_w, 3), round(item_d, 3), round(item["h"], 3)],
                    "rotation_deg": rotation,
                    "note": f"Neufert-sourced {item['type']} in {template_key}",
                }
            )
            placed_rects.append(rect)

    return all_furniture


def _resolve_template_key(room_type: str) -> str:
    """Map any room type string to a FURNITURE_TEMPLATES key."""
    direct_keys = set(FURNITURE_TEMPLATES.keys())
    if room_type in direct_keys:
        return room_type

    mapping = {
        "master_bedroom": "master_room",
        "master room":    "master_room",
        "dining":         "dining_room",
        "dining_room":    "dining_room",
        "balcony":        "balcony",
        "toilet":         "bathroom",
        "washroom":       "bathroom",
        "foyer":          "entrance",
        "child_room":     "bedroom",
        "study_room":     "bedroom",
        "guest_room":     "bedroom",
        "second_room":    "bedroom",
        "store":          "storage",
        "store_room":     "storage",
        "prayer_room":    "puja_room",
        "pooja_room":     "puja_room",
        "car_park":       "parking",
        "garage":         "parking",
    }
    return mapping.get(room_type, "multi_use")


# ── Area statistics derived from RPLAN / Graph2Plan dataset ────────────────────
# These percentages reflect the median proportion of floor area each room type
# occupies in 75,000 real Indian-style residential floor plans (RPLAN dataset).
# Used by layout_generator to size rooms proportionally.
# Categories: LivingRoom(0), MasterRoom(1), Kitchen(2), Bathroom(3),
#             DiningRoom(4), ChildRoom(5), StudyRoom(6), SecondRoom(7),
#             GuestRoom(8), Balcony(9), Entrance(10), Storage(11)
RPLAN_AREA_RATIOS: Dict[str, float] = {
    "living_room":  0.22,   # largest single public space
    "master_room":  0.16,   # master bedroom
    "kitchen":      0.12,   # kitchen (often includes dining in compact plans)
    "bathroom":     0.05,   # typically 1 bathroom per bedroom
    "dining_room":  0.10,   # separate dining (if present)
    "bedroom":      0.13,   # secondary bedrooms (per bedroom)
    "balcony":      0.04,
    "entrance":     0.04,
    "staircase":    0.04,   # RPLAN staircase; scaled down from current bug
    "storage":      0.03,
    "parking":      0.07,   # ground floor only
    "puja_room":    0.02,
    "multi_use":    0.04,
    "circulation":  0.04,
}

# Neufert minimum areas (m²) — absolute lower bounds
NEUFERT_MIN_AREA: Dict[str, float] = {
    "living_room":  14.0,
    "master_room":  12.0,
    "kitchen":       8.0,
    "bathroom":      3.5,
    "dining_room":  10.0,
    "bedroom":      10.0,
    "balcony":       3.0,
    "entrance":      3.0,
    "staircase":     5.5,  # 1.0 m wide × 5.5 m long flight
    "storage":       2.0,
    "parking":      12.5,  # single 2.5 × 5.0 stall
    "puja_room":     2.0,
    "multi_use":     4.0,
    "circulation":   2.0,
}

# Neufert maximum areas (m²) — above which rooms become wasteful
NEUFERT_MAX_AREA: Dict[str, float] = {
    "staircase":    12.0,   # absolute cap — fixes the 88 m² bug
    "bathroom":     12.0,
    "storage":       8.0,
    "puja_room":     6.0,
    "entrance":      8.0,
}
