"""
services/bylaw_loader.py — Building Bylaw Loader
=================================================

PURPOSE:
    Loads the correct set of building bylaws (setbacks, FAR limits, height
    limits, etc.) for a given region and building type from JSON data files.

DESIGN PRINCIPLE:
    This service has ZERO Django or LLM dependencies — it is pure Python.
    This means you can test it independently without starting Django.

HOW IT WORKS:
    1. You call `detect_region("Mumbai, India")` → returns "india_mumbai"
    2. You call `load_bylaws("india_mumbai", "residential")` → returns a
       `BylawRuleset` dataclass with all the numbers you need.
    3. If the region JSON file doesn't exist → falls back to "default.json"
    4. If the building_type doesn't exist in the JSON → falls back to "residential"

HOW TO ADD A NEW REGION:
    1. Create a new file in backend/bylaws/  e.g., india_pune.json
    2. Copy the structure from india_mumbai.json and edit the values
    3. Add keywords to REGION_KEYWORDS so the detector can find it:
           "india_pune": ["pune", "pimpri", "pcmc"]
    4. That's it — no code changes needed elsewhere.

HOW TO DEBUG:
    - Print `detect_region("your location")` to see which region_id is returned
    - Print `load_bylaws(region_id)` to inspect all loaded values
    - Check that your JSON file is valid JSON (use jsonlint.com if unsure)
    - Common mistake: forgetting to add keywords to REGION_KEYWORDS

USAGE EXAMPLE:
    from services.bylaw_loader import detect_region, load_bylaws

    region_id = detect_region("Mumbai")       # → "india_mumbai"
    bylaws = load_bylaws(region_id)           # → BylawRuleset(...)
    print(bylaws.setback_front_m)             # → 3.0
    print(bylaws.max_far)                     # → 1.5
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Path Resolution ────────────────────────────────────────────────────────────
# BYLAWS_DIR is resolved relative to this file's location.
# File location: backend/services/bylaw_loader.py
# Bylaw files:   backend/bylaws/*.json
# So we go up one level (.parent) from services/ to get to backend/
BYLAWS_DIR = Path(__file__).resolve().parent.parent / "bylaws"


# ── Data Classes ───────────────────────────────────────────────────────────────
# We use Python dataclasses to represent bylaw data as typed objects.
# This gives us auto-generated __repr__, type hints, and IDE autocomplete.
# Think of these as simple "named containers" for grouped data.

@dataclass
class ParkingRules:
    """
    Parking space requirements for a building type.

    FIELDS:
      min_stalls_per_unit  → Minimum parking stalls per residential unit
                             (or per 100 sq.m for commercial)
      stall_width_m        → Width of one parking stall in metres
      stall_depth_m        → Depth of one parking stall in metres
      aisle_width_m        → Width of the driving aisle between rows of stalls
      notes                → Any special notes from the bylaw

    EXAMPLE (Mumbai residential):
      ParkingRules(min_stalls_per_unit=1.0, stall_width_m=2.5, ...)
    """
    min_stalls_per_unit: float = 1.0
    stall_width_m: float = 2.5
    stall_depth_m: float = 5.0
    aisle_width_m: float = 3.5
    notes: str = ""


@dataclass
class BylawRuleset:
    """
    A complete set of building bylaws for one region + building type combination.

    All distances are in METRES (m).
    All areas are in SQUARE METRES (sq.m).
    Percentages are stored as plain numbers (50.0 means 50%).

    FIELDS:
      region_id              → Machine-readable ID matching the JSON filename
                               e.g., "india_mumbai"
      region_name            → Human-readable name for display
                               e.g., "India — Mumbai (DCPR 2034)"
      building_type          → "residential" or "commercial"
      setback_front_m        → Minimum distance from front plot boundary to building
                               (The "front" faces the road/street)
      setback_rear_m         → Minimum distance from rear plot boundary to building
      setback_side_m         → Minimum distance from each SIDE plot boundary to building
      max_far                → Maximum Floor Area Ratio
                               FAR = Total Built-up Area / Plot Area
                               If FAR = 1.5 and plot = 1200 sq.m → max built area = 1800 sq.m
      max_height_m           → Maximum total building height from ground level
      max_floors             → Maximum number of floors (Ground = Floor 1)
      max_plot_coverage_pct  → Maximum % of plot area that the building footprint covers
                               If 50% and plot = 1200 sq.m → footprint ≤ 600 sq.m
      floor_height_m         → Standard floor-to-floor height for height calculations
      parking                → Parking requirements (see ParkingRules above)
      notes                  → Human-readable notes / caveats from the JSON file

    EXAMPLE:
      BylawRuleset(
          region_id="india_mumbai",
          region_name="India — Mumbai (DCPR 2034)",
          building_type="residential",
          setback_front_m=3.0,
          ...
      )
    """
    region_id: str
    region_name: str
    building_type: str
    setback_front_m: float
    setback_rear_m: float
    setback_side_m: float
    max_far: float
    max_height_m: float
    max_floors: int
    max_plot_coverage_pct: float
    floor_height_m: float = 3.0
    parking: ParkingRules = field(default_factory=ParkingRules)
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to a plain dictionary (for JSON serialization in API response)."""
        return {
            "region_id": self.region_id,
            "region_name": self.region_name,
            "building_type": self.building_type,
            "setback_front_m": self.setback_front_m,
            "setback_rear_m": self.setback_rear_m,
            "setback_side_m": self.setback_side_m,
            "max_far": self.max_far,
            "max_height_m": self.max_height_m,
            "max_floors": self.max_floors,
            "max_plot_coverage_pct": self.max_plot_coverage_pct,
            "floor_height_m": self.floor_height_m,
            "parking": {
                "min_stalls_per_unit": self.parking.min_stalls_per_unit,
                "stall_width_m": self.parking.stall_width_m,
                "stall_depth_m": self.parking.stall_depth_m,
                "aisle_width_m": self.parking.aisle_width_m,
                "notes": self.parking.notes,
            },
            "notes": self.notes,
        }


# ── Region Detection ───────────────────────────────────────────────────────────
# Maps each region_id to a list of lowercase keywords.
# detect_region() checks if any keyword appears in the location string.
#
# HOW TO ADD A NEW REGION:
#   "india_pune": ["pune", "pimpri", "chinchwad", "pcmc"],
#
REGION_KEYWORDS: Dict[str, List[str]] = {
    "india_mumbai": ["mumbai", "bombay", "maharashtra", "thane", "navi mumbai"],
    "india_delhi":  ["delhi", "new delhi", "ncr", "ndmc", "gurugram", "noida", "gurgaon"],
    "usa_nyc":      ["new york", "nyc", "manhattan", "brooklyn", "queens", "bronx", "staten island"],
}


def detect_region(location_string: str) -> str:
    """
    Detect a region_id from a free-text location string.

    This is a simple keyword-matching approach. In Phase 2, the LLM
    (Ollama) will pre-process the location to a clean string.

    Args:
        location_string: Any location text, e.g., "Mumbai", "New York City",
                         "Delhi NCR", or even "somewhere in Maharashtra"

    Returns:
        A region_id string that corresponds to a bylaw JSON file.
        Returns "default" if no match is found.

    Examples:
        detect_region("Mumbai")          → "india_mumbai"
        detect_region("New York City")   → "usa_nyc"
        detect_region("Pune")            → "default"  (not in keywords yet)
        detect_region("")                → "default"

    DEBUGGING:
        If a known city isn't detected, add its keywords to REGION_KEYWORDS above.
    """
    if not location_string:
        return "default"

    location_lower = location_string.lower().strip()

    for region_id, keywords in REGION_KEYWORDS.items():
        if any(keyword in location_lower for keyword in keywords):
            return region_id

    # No match found → use conservative defaults
    return "default"


def list_available_regions() -> List[str]:
    """
    Return a list of all available region_ids (from matching JSON files).

    Useful for:
      - API endpoint that lists supported regions
      - Validation: check if user-supplied region_id is valid
      - Admin UI dropdown

    Returns:
        List of region_id strings (filename without .json)
        e.g., ["default", "india_delhi", "india_mumbai", "usa_nyc"]
    """
    if not BYLAWS_DIR.exists():
        return ["default"]
    return sorted(
        f.stem for f in BYLAWS_DIR.glob("*.json")
    )


def load_bylaws(region_id: str, building_type: str = "residential") -> BylawRuleset:
    """
    Load and return the BylawRuleset for a given region + building type.

    Args:
        region_id:      e.g., "india_mumbai", "usa_nyc", "default"
                        Use detect_region() to get this from a location string.
        building_type:  "residential" (default) or "commercial"

    Returns:
        BylawRuleset dataclass with all validated, typed bylaw values.

    Raises:
        FileNotFoundError: If neither the region file nor default.json exists.
                           This should never happen in normal operation.

    BEHAVIOUR:
      1. Looks for backend/bylaws/{region_id}.json
      2. If not found → prints a warning and loads default.json instead
      3. If building_type not in file → prints a warning and uses "residential"
      4. Parses the JSON and returns a typed BylawRuleset

    DEBUGGING:
      - "Warning: No bylaw file for X" → Add a JSON file or update keywords
      - "Warning: Building type X not found" → Add the type to the JSON file
      - JSONDecodeError → Your JSON file has a syntax error (check with jsonlint.com)
    """
    bylaw_file = BYLAWS_DIR / f"{region_id}.json"

    # Fall back to default if specific region file not found
    if not bylaw_file.exists():
        print(f"[BylawLoader] ⚠️  No bylaw file for region '{region_id}'. Using default.json.")
        bylaw_file = BYLAWS_DIR / "default.json"
        region_id = "default"

    with open(bylaw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    building_types = data.get("building_types", {})

    # Fall back to residential if requested building type not found
    if building_type not in building_types:
        print(f"[BylawLoader] ⚠️  Building type '{building_type}' not found. Using 'residential'.")
        building_type = "residential"

    bt = building_types[building_type]
    parking_data = bt.get("parking", {})

    return BylawRuleset(
        region_id=data["region_id"],
        region_name=data["region_name"],
        building_type=building_type,
        setback_front_m=float(bt["setback_front_m"]),
        setback_rear_m=float(bt["setback_rear_m"]),
        setback_side_m=float(bt["setback_side_m"]),
        max_far=float(bt["max_far"]),
        max_height_m=float(bt["max_height_m"]),
        max_floors=int(bt["max_floors"]),
        max_plot_coverage_pct=float(bt["max_plot_coverage_pct"]),
        floor_height_m=float(bt.get("floor_height_m", 3.0)),
        parking=ParkingRules(
            min_stalls_per_unit=float(parking_data.get("min_stalls_per_unit", 1.0)),
            stall_width_m=float(parking_data.get("stall_width_m", 2.5)),
            stall_depth_m=float(parking_data.get("stall_depth_m", 5.0)),
            aisle_width_m=float(parking_data.get("aisle_width_m", 3.5)),
            notes=str(parking_data.get("notes", "")),
        ),
        notes="; ".join(str(n) for n in bt.get("_notes", [])),
    )
