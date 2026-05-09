"""Structured optimization brief generation for presentation-ready outputs."""

from __future__ import annotations

from collections import Counter
import hashlib
from typing import Any, Dict, List


PRIORITIES = [
    "Max usable area",
    "Minimal circulation waste",
    "Logical zoning and adjacency",
    "Good daylight and cross ventilation",
    "Clean structural grid",
    "Premium modern aesthetics",
    "Realistic, buildable geometry",
]


RULES = [
    "No dead space",
    "No random complexity",
    "Efficient room proportions",
    "Clear public and private zoning",
    "Balanced facade rhythm",
    "Smart window placement",
    "Compact massing",
    "Future-flexible layout",
]


def _clean_room_name(room_type: str) -> str:
    value = str(room_type or "").strip().lower()
    if "bed" in value:
        return "bedroom"
    if "bath" in value or "wash" in value or "toilet" in value:
        return "bathroom"
    return value or "space"


def _to_title(token: str) -> str:
    return str(token or "").replace("_", " ").strip().title()


def _site_size_text(parsed_input: Dict[str, Any]) -> str:
    width = float(parsed_input.get("plot_width_m", 0.0) or 0.0)
    depth = float(parsed_input.get("plot_depth_m", 0.0) or 0.0)
    area = width * depth
    return f"{width:g}m x {depth:g}m ({area:.1f} sqm)"


def _variant_index(parsed_input: Dict[str, Any], key: str, modulo: int) -> int:
    if modulo <= 0:
        return 0
    base = "|".join(
        [
            str(parsed_input.get("raw_text", "") or ""),
            str(parsed_input.get("region", "") or ""),
            str(parsed_input.get("building_type", "") or ""),
            str(parsed_input.get("plot_width_m", "") or ""),
            str(parsed_input.get("plot_depth_m", "") or ""),
            str(parsed_input.get("num_floors", "") or ""),
            key,
        ]
    )
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _pick_variant(parsed_input: Dict[str, Any], key: str, variants: List[str]) -> str:
    if not variants:
        return ""
    idx = _variant_index(parsed_input, key, len(variants))
    return variants[idx]


def _space_summary(parsed_input: Dict[str, Any], layout_zones: List[dict]) -> List[str]:
    source_rooms = parsed_input.get("rooms") or []
    rooms = [
        _clean_room_name(str(room))
        for room in source_rooms
        if str(room).strip()
    ]

    if not rooms:
        rooms = [
            _clean_room_name(str(zone.get("room_type", "")))
            for zone in layout_zones
            if str(zone.get("room_type", "")).strip()
        ]

    filtered = [room for room in rooms if room not in {"circulation", "multi_use"}]
    counts = Counter(filtered)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [f"{count}x {_to_title(name)}" for name, count in ordered]


def _special_requirements(parsed_input: Dict[str, Any], compliance_report: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    preferences = parsed_input.get("preferences")
    if isinstance(preferences, dict):
        for key, value in sorted(preferences.items()):
            if value:
                items.append(_to_title(str(key)))

    if parsed_input.get("use_vastu"):
        items.append("Vastu preference")

    required_stalls = compliance_report.get("required_parking_stalls")
    if isinstance(required_stalls, (int, float)):
        items.append(f"Parking capacity for {int(required_stalls)} stall(s)")

    deduped: List[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _zoning_note(parsed_input: Dict[str, Any], layout_zones: List[dict], floors: int) -> str:
    if not layout_zones:
        return (
            "Zoning intent is prepared with a public-to-private hierarchy, "
            "and will finalize once full spatial inputs are confirmed."
        )

    rooms_by_floor: Dict[int, set[str]] = {}
    for zone in layout_zones:
        floor = int(zone.get("floor", 0))
        room = _clean_room_name(str(zone.get("room_type", "")))
        rooms_by_floor.setdefault(floor, set()).add(room)

    ground_rooms = rooms_by_floor.get(0, set())
    upper_rooms = set()
    for floor in range(1, floors):
        upper_rooms.update(rooms_by_floor.get(floor, set()))

    public_terms = sorted(ground_rooms.intersection({"living_room", "kitchen", "parking"}))
    private_terms = sorted(upper_rooms.intersection({"bedroom", "study", "family_lounge"}))

    public_text = ", ".join(_to_title(term) for term in public_terms) or "public program"
    private_text = ", ".join(_to_title(term) for term in private_terms) or "private program"

    variants = [
        f"Ground floor prioritizes {public_text} near entry access, while upper levels organize {private_text} for privacy and logical vertical zoning.",
        f"Public-facing uses ({public_text}) are anchored at arrival level, with upper-storey {private_text} arranged as quieter private zones.",
        f"Zoning sequence keeps {public_text} at primary access level and shifts {private_text} upward to maintain a clear public-private gradient.",
    ]
    return _pick_variant(parsed_input, "zoning_note", variants)


def _circulation_note(parsed_input: Dict[str, Any], layout_metrics: Dict[str, Any]) -> str:
    floor_metrics = layout_metrics.get("floor_metrics") or []
    if not floor_metrics:
        return "Circulation is planned as a compact primary spine with minimal travel distance."

    avg = sum(float(item.get("circulation_score", 0.0)) for item in floor_metrics) / len(floor_metrics)
    if avg >= 80:
        quality = "highly efficient"
    elif avg >= 60:
        quality = "efficient with minor refinement opportunities"
    else:
        quality = "workable but should be refined to reduce travel inefficiencies"

    variants = [
        f"Circulation strategy is {quality} (avg score {avg:.1f}/100), using short connectors and direct vertical core access to limit wasted corridor area.",
        f"Movement planning rates {quality} at {avg:.1f}/100, with compact path lengths and a legible core to reduce circulation loss.",
        f"Access flow is {quality} ({avg:.1f}/100), balancing short travel routes with direct core links for better usable-area efficiency.",
    ]
    return _pick_variant(parsed_input, "circulation_note", variants)


def _daylight_note(parsed_input: Dict[str, Any], layout_zones: List[dict]) -> str:
    if not layout_zones:
        return "Daylight and cross-ventilation intent is enabled by dual-aspect planning where feasible."

    zones_by_floor: Dict[int, List[dict]] = {}
    for zone in layout_zones:
        floor = int(zone.get("floor", 0))
        zones_by_floor.setdefault(floor, []).append(zone)

    cross_vent_floors = 0
    for floor_zones in zones_by_floor.values():
        orientations = {
            str(item.get("orientation", "")).lower()
            for item in floor_zones
            if str(item.get("orientation", "")).strip()
        }
        has_ns = any("north" in value for value in orientations) and any("south" in value for value in orientations)
        has_ew = any("east" in value for value in orientations) and any("west" in value for value in orientations)
        if has_ns or has_ew:
            cross_vent_floors += 1

    total_floors = len(zones_by_floor)
    variants = [
        f"Daylight strategy uses orientation-aware openings and supports cross-ventilation on {cross_vent_floors}/{total_floors} floor(s) through opposing facade exposure.",
        f"Facade opening logic improves daylight depth and enables cross-flow on {cross_vent_floors}/{total_floors} floor(s) via opposite-side exposure.",
        f"Climate response prioritizes controlled daylight and cross-vent potential across {cross_vent_floors}/{total_floors} floor(s) with dual-aspect facade access.",
    ]
    return _pick_variant(parsed_input, "daylight_note", variants)


def _geometry_note(parsed_input: Dict[str, Any], geometry_validation: Dict[str, Any] | None) -> str:
    if geometry_validation is None:
        variants = [
            "Geometry is targeted to remain clean, compact, and construction-ready.",
            "Spatial envelopes are kept disciplined and build-ready, avoiding unnecessary form complexity.",
        ]
        return _pick_variant(parsed_input, "geometry_unknown", variants)
    if geometry_validation.get("valid"):
        variants = [
            "Geometry validation passed, confirming realistic and buildable spatial envelopes.",
            "Validation checks passed: geometry remains practical for execution and downstream model handoff.",
            "Buildability checks succeeded, indicating coherent, constructible geometry with no blocking conflicts.",
        ]
        return _pick_variant(parsed_input, "geometry_valid", variants)
    issues = geometry_validation.get("overlap_issues") or []
    variants = [
        "Geometry requires refinement to remove overlap conflicts "
        f"({len(issues)} issue(s) detected) before final 3D delivery.",
        f"Current geometry has {len(issues)} blocking overlap issue(s); resolve these before final Hypar/3D export.",
        f"Constructability risk detected: {len(issues)} overlap issue(s) must be corrected prior to presentation-ready output.",
    ]
    return _pick_variant(parsed_input, "geometry_invalid", variants)


def _requirement_examples(building_type: str) -> List[str]:
    if building_type == "commercial":
        return [
            "Design a 6-floor commercial office in NYC on a 45x60m plot with 2 basement parking levels and high daylight floors.",
            "Create a G+4 mixed-use commercial block in Mumbai on 30x50m with retail on ground and office floors above.",
            "Plan a 5-floor business center in Delhi on 40x40m plot with service core in center and shaded west facade.",
            "Generate a compact corporate campus building on 55x35m with reception atrium, meeting floors, and compliant parking.",
        ]
    return [
        "Design a 2-floor residential house in Mumbai on a 30x40m plot with parking and good cross ventilation.",
        "Create a 3-floor home in Delhi on 25x45m site with 4 bedrooms, balcony, and compact circulation.",
        "Plan a vastu-aware duplex in Mumbai on 36x24m plot with parking, family lounge, and private upper floor bedrooms.",
        "Design a modern villa in NYC on 28x35m lot with clear public/private zoning, daylight-focused facade, and buildable geometry.",
    ]


def build_optimized_design_brief(
    parsed_input: Dict[str, Any],
    compliance_report: Dict[str, Any],
    layout_zones: List[dict],
    layout_metrics: Dict[str, Any],
    geometry_validation: Dict[str, Any] | None,
    requires_clarification: bool = False,
) -> Dict[str, Any]:
    floors = int(compliance_report.get("adjusted_floors", parsed_input.get("num_floors", 1)) or 1)
    building_type = str(parsed_input.get("building_type", "residential") or "residential")
    parking_requested = False

    preferences = parsed_input.get("preferences")
    if isinstance(preferences, dict):
        parking_requested = bool(preferences.get("parking"))
    if not parking_requested:
        parking_requested = any(
            _clean_room_name(str(zone.get("room_type", ""))) == "parking"
            for zone in layout_zones
        )

    if requires_clarification:
        presentation_summary = _pick_variant(
            parsed_input,
            "presentation_clarification",
            [
                "Modern, elegant, climate-aware concept is staged and waiting for missing inputs to finalize presentation-ready 3D geometry.",
                "Initial concept is prepared; provide remaining project details to unlock full climate-aware, presentation-grade 3D output.",
                "Design intent is established, but additional input is needed before final buildable geometry and polished 3D handoff.",
            ],
        )
    else:
        presentation_summary = _pick_variant(
            parsed_input,
            "presentation_ready",
            [
                "Modern, elegant, climate-aware, presentation-ready 3D design with compact massing, clear zoning, and buildable geometry.",
                "Presentation-grade concept achieved with modern facade discipline, climate-aware planning, and practical buildable form.",
                "Refined 3D concept is ready for review: compact massing, efficient zoning logic, and execution-friendly geometry.",
            ],
        )

    optimization_note = _pick_variant(
        parsed_input,
        "optimization_note",
        [
            "Plan targets high usable-area efficiency with repeatable room modules, minimal residual pockets, and adaptable floor programming for future changes.",
            "Layout strategy emphasizes net-usable area gains using disciplined module repetition and low-circulation-loss organization.",
            "Optimization focus remains on efficient room proportions, compact massing, and future-flexible planning without dead pockets.",
        ],
    )

    structural_grid_note = _pick_variant(
        parsed_input,
        "structural_grid_note",
        [
            "A clean, repeatable structural grid is maintained to align walls, services, and spans for cost-efficient construction and facade rhythm consistency.",
            "Structural planning uses a consistent grid language to simplify spans, service alignment, and construction sequencing.",
            "Grid coherence is preserved across floors to support straightforward execution, service coordination, and facade order.",
        ],
    )

    aesthetic_note = _pick_variant(
        parsed_input,
        "aesthetic_note",
        [
            "Facade language remains premium and modern through controlled solids-voids balance, proportion discipline, and restrained material articulation.",
            "Aesthetic direction stays contemporary and premium, using measured facade rhythm, depth, and balanced opening hierarchy.",
            "Visual identity favors modern clarity with controlled composition, coherent proportions, and non-excessive detailing.",
        ],
    )

    guidance = (
        "Write requirements with: city/region, plot size, floors, building type, must-have spaces, parking intent, and any special preferences (for example: vastu, balcony, daylight priority)."
    )

    return {
        "project_type": _to_title(building_type),
        "site_size": _site_size_text(parsed_input),
        "spaces": _space_summary(parsed_input, layout_zones),
        "floors": floors,
        "parking": "Included" if parking_requested else "Not explicitly requested",
        "special_requirements": _special_requirements(parsed_input, compliance_report),
        "requirements_guidance": guidance,
        "requirement_examples": _requirement_examples(building_type),
        "priorities": PRIORITIES,
        "rules": RULES,
        "zoning_note": _zoning_note(parsed_input, layout_zones, floors),
        "circulation_note": _circulation_note(parsed_input, layout_metrics),
        "optimization_note": optimization_note,
        "daylight_ventilation_note": _daylight_note(parsed_input, layout_zones),
        "structural_grid_note": structural_grid_note,
        "aesthetic_note": aesthetic_note,
        "geometry_note": _geometry_note(parsed_input, geometry_validation),
        "presentation_summary": presentation_summary,
    }
