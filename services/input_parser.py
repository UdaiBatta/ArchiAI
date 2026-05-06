"""Input parsing utilities with optional Ollama support.

This module keeps natural language understanding isolated from compliance logic.
If Ollama is unavailable, deterministic heuristics are used as a safe fallback.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Tuple

from services.bylaw_loader import detect_region

DEFAULT_INPUT: Dict[str, Any] = {
    "region": "default",
    "building_type": "residential",
    "plot_width_m": 30.0,
    "plot_depth_m": 40.0,
    "num_floors": 2,
    "num_units": 1,
    "rooms": [],
    "preferences": {},
    "plot_facing_direction": "north",
    "use_vastu": False,
}

ALLOWED_BUILDING_TYPES = {"residential", "commercial"}
ALLOWED_DIRECTIONS = {
    "north",
    "south",
    "east",
    "west",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
}

REQUIRED_FIELDS = [
    "region",
    "building_type",
    "plot_width_m",
    "plot_depth_m",
    "num_floors",
]

FIELD_QUESTIONS = {
    "region": "Which city or region should I use for building bylaws?",
    "building_type": "What type of building do you want to design?",
    "plot_width_m": "What is the plot width (in meters)?",
    "plot_depth_m": "What is the plot depth (in meters)?",
    "num_floors": "How many floors do you want?",
    "plot_facing_direction": "Which direction does the plot face (for Vastu planning)?",
}

PREFERENCE_KEYWORDS = {
    "parking": ["parking", "car park", "carport", "garage"],
    "balcony": ["balcony", "sitout", "deck"],
    "open_kitchen": ["open kitchen", "island kitchen"],
    "staircase": ["stair", "staircase", "duplex stair"],
    "puja_room": ["puja", "pooja", "prayer room", "mandir"],
}

ROOM_KEYWORDS = {
    "living_room": ["living", "living room", "lounge"],
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom", "bed room", "bhk"],
    "bathroom": ["bathroom", "washroom", "toilet"],
    "parking": ["parking", "garage", "carport"],
    "balcony": ["balcony", "sitout", "deck"],
    "staircase": ["stair", "staircase"],
    "puja_room": ["puja", "pooja", "prayer room", "mandir"],
}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return True
    return False

def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _extract_plot_size(raw_text: str) -> Tuple[float | None, float | None]:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:x|X|×|by)\s*(\d+(?:\.\d+)?)",
        r"plot\s*(?:of|size)?\s*(\d+(?:\.\d+)?)\s*(?:m|meter|metre)?\s*(?:x|X|×|by)\s*(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            width = _safe_float(match.group(1), 0.0)
            depth = _safe_float(match.group(2), 0.0)
            if width > 0 and depth > 0:
                return width, depth
    return None, None


def _extract_floor_count(raw_text: str) -> int | None:
    patterns = [
        r"(\d+)\s*[- ]?(?:floor|floors|storey|storeys|story|stories)",
        r"(?:g\+)?(\d+)\s*(?:house|building)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            floors = _safe_int(match.group(1), 0)
            if floors > 0:
                return floors
    return None


def _extract_bedroom_count(raw_text: str) -> int | None:
    patterns = [
        r"(\d+)\s*(?:bed(?:room)?s?)",
        r"(\d+)\s*bhk",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            count = _safe_int(match.group(1), 0)
            if count > 0:
                return count
    return None


def _extract_units(raw_text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:units?|flats?|apartments?)", raw_text)
    if match:
        count = _safe_int(match.group(1), 0)
        if count > 0:
            return count
    return None


def _extract_direction(raw_text: str) -> str | None:
    direction_aliases = {
        "north east": "northeast",
        "north-west": "northwest",
        "north west": "northwest",
        "south-east": "southeast",
        "south east": "southeast",
        "south-west": "southwest",
        "south west": "southwest",
    }

    normalized = raw_text
    for alias, canonical in direction_aliases.items():
        normalized = normalized.replace(alias, canonical)

    for direction in sorted(ALLOWED_DIRECTIONS, key=len, reverse=True):
        if direction in normalized:
            return direction
    return None


def _extract_keywords(raw_text: str) -> Tuple[Dict[str, bool], list[str], bool]:
    preferences: Dict[str, bool] = {}
    rooms: list[str] = []

    for key, variants in PREFERENCE_KEYWORDS.items():
        if any(variant in raw_text for variant in variants):
            preferences[key] = True

    for room_type, variants in ROOM_KEYWORDS.items():
        if any(variant in raw_text for variant in variants):
            rooms.append(room_type)

    use_vastu = "vastu" in raw_text or "vaastu" in raw_text
    return preferences, rooms, use_vastu


def _normalize_ollama_json(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}

    region = str(data.get("region", "")).strip().lower()
    if region:
        normalized["region"] = region

    building_type = str(data.get("building_type", "")).strip().lower()
    if building_type in ALLOWED_BUILDING_TYPES:
        normalized["building_type"] = building_type

    width = _safe_float(data.get("plot_width_m"), 0.0)
    depth = _safe_float(data.get("plot_depth_m"), 0.0)
    if width > 0:
        normalized["plot_width_m"] = width
    if depth > 0:
        normalized["plot_depth_m"] = depth

    floors = _safe_int(data.get("num_floors"), 0)
    if floors > 0:
        normalized["num_floors"] = floors

    units = _safe_int(data.get("num_units"), 0)
    if units > 0:
        normalized["num_units"] = units

    rooms = data.get("rooms") or []
    if isinstance(rooms, list):
        normalized["rooms"] = [str(room).strip().lower() for room in rooms if str(room).strip()]

    preferences = data.get("preferences") or {}
    if isinstance(preferences, dict):
        normalized["preferences"] = {
            str(k).strip().lower(): bool(v) for k, v in preferences.items()
        }

    direction = str(data.get("plot_facing_direction", "")).strip().lower()
    if direction in ALLOWED_DIRECTIONS:
        normalized["plot_facing_direction"] = direction

    if isinstance(data.get("use_vastu"), bool):
        normalized["use_vastu"] = data["use_vastu"]

    return normalized


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def _try_ollama_parse(raw_text: str, model: str, host: str) -> Tuple[Dict[str, Any], str]:
    if not raw_text.strip():
        return {}, "skipped"

    try:
        from ollama import Client
    except Exception:
        return {}, "not_installed"

    parser_prompt = (
        "Extract building requirements into strict JSON with keys: "
        "region, building_type, plot_width_m, plot_depth_m, num_floors, "
        "num_units, rooms, preferences, plot_facing_direction, use_vastu. "
        "Return only JSON."
    )

    try:
        client = Client(host=host)
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": parser_prompt},
                {"role": "user", "content": raw_text},
            ],
            options={"temperature": 0},
        )
        content = response.get("message", {}).get("content", "")
        payload = json.loads(_strip_json_fence(content))
        if not isinstance(payload, dict):
            return {}, "invalid_payload"
        return _normalize_ollama_json(payload), "ok"
    except Exception:
        return {}, "unavailable"


def check_ollama_status(host: str, model: str) -> str:
    try:
        from ollama import Client
    except Exception:
        return "not_installed"

    try:
        client = Client(host=host)
        client.list()
        # Presence of the model is not mandatory for health to pass.
        return f"reachable (model: {model})"
    except Exception:
        return "unreachable"


def check_missing_fields(parsed_data: dict) -> list[str]:
    missing_fields: list[str] = []

    inferred = set(parsed_data.get("_inferred_fields", []))

    for field in REQUIRED_FIELDS:
        if field in inferred or is_missing(parsed_data.get(field)):
            if field not in missing_fields:
                missing_fields.append(field)

    if parsed_data.get("use_vastu") is True:
        if "plot_facing_direction" in inferred or is_missing(
            parsed_data.get("plot_facing_direction")
        ):
            if "plot_facing_direction" not in missing_fields:
                missing_fields.append("plot_facing_direction")

    return missing_fields


def generate_clarification_questions(parsed_data: dict) -> list[str]:
    missing_fields = check_missing_fields(parsed_data)

    questions: list[str] = []
    for field in missing_fields:
        question = FIELD_QUESTIONS.get(field)
        if question:
            questions.append(question)

    return questions


def parse_design_input(
    incoming_data: Dict[str, Any],
    ollama_model: str,
    ollama_host: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse and normalize request input into structured fields.

    Priority:
    1. Explicit structured request values
    2. Ollama extracted values (if available)
    3. Regex/keyword heuristics from raw text
    4. Static defaults
    """

    incoming_payload = dict(incoming_data or {})
    explicit_fields_override = incoming_payload.pop("_explicit_fields", None)

    structured = dict(DEFAULT_INPUT)
    structured.update(incoming_payload)

    if isinstance(explicit_fields_override, (list, tuple, set)):
        explicit_fields = {str(field) for field in explicit_fields_override}
    else:
        explicit_fields = {
            key for key, value in incoming_payload.items() if not is_missing(value)
        }

    raw_text = str(structured.get("raw_text", "") or "")
    raw_lower = raw_text.lower()

    heuristic: Dict[str, Any] = {}
    width, depth = _extract_plot_size(raw_lower)
    if width and depth:
        heuristic["plot_width_m"] = width
        heuristic["plot_depth_m"] = depth

    floors = _extract_floor_count(raw_lower)
    if floors:
        heuristic["num_floors"] = floors

    units = _extract_units(raw_lower)
    if units:
        heuristic["num_units"] = units

    bedrooms = _extract_bedroom_count(raw_lower)
    if bedrooms:
        heuristic["rooms"] = ["bedroom"] * bedrooms

    direction = _extract_direction(raw_lower)
    if direction:
        heuristic["plot_facing_direction"] = direction

    inferred_region = detect_region(raw_lower)
    if inferred_region != "default":
        heuristic["region"] = inferred_region

    preferences, rooms_from_keywords, vastu_from_text = _extract_keywords(raw_lower)
    if preferences:
        heuristic["preferences"] = preferences
    if rooms_from_keywords:
        heuristic.setdefault("rooms", []).extend(rooms_from_keywords)
    if vastu_from_text:
        heuristic["use_vastu"] = True

    ollama_data, ollama_status = _try_ollama_parse(raw_text, ollama_model, ollama_host)

    replaceable_defaults = {
        "region": "default",
        "building_type": "residential",
        "plot_width_m": 30.0,
        "plot_depth_m": 40.0,
        "num_floors": 2,
        "num_units": 1,
        "rooms": [],
        "preferences": {},
        "plot_facing_direction": "north",
        "use_vastu": False,
    }

    for source in (heuristic, ollama_data):
        for key, value in source.items():
            if key not in structured:
                structured[key] = value
                continue

            current_value = structured.get(key)
            default_value = replaceable_defaults.get(key)

            if isinstance(current_value, list):
                merged = list(current_value)
                for item in value if isinstance(value, list) else []:
                    if item not in merged:
                        merged.append(item)
                structured[key] = merged
            elif isinstance(current_value, dict):
                merged = dict(current_value)
                if isinstance(value, dict):
                    merged.update(value)
                structured[key] = merged
            elif current_value == default_value:
                structured[key] = value

    structured["region"] = str(structured.get("region", "default") or "default").lower()
    if structured["region"] == "default" and raw_text:
        structured["region"] = detect_region(raw_lower)

    building_type = str(structured.get("building_type", "residential") or "residential").lower()
    structured["building_type"] = (
        building_type if building_type in ALLOWED_BUILDING_TYPES else "residential"
    )

    structured["plot_width_m"] = max(1.0, _safe_float(structured.get("plot_width_m"), 30.0))
    structured["plot_depth_m"] = max(1.0, _safe_float(structured.get("plot_depth_m"), 40.0))
    structured["num_floors"] = max(1, _safe_int(structured.get("num_floors"), 2))
    structured["num_units"] = max(1, _safe_int(structured.get("num_units"), 1))

    direction = str(structured.get("plot_facing_direction", "north") or "north").lower()
    structured["plot_facing_direction"] = direction if direction in ALLOWED_DIRECTIONS else "north"

    if not isinstance(structured.get("rooms"), list):
        structured["rooms"] = []
    structured["rooms"] = [
        str(room).strip().lower() for room in structured["rooms"] if str(room).strip()
    ]

    if not isinstance(structured.get("preferences"), dict):
        structured["preferences"] = {}

    structured["use_vastu"] = bool(
        structured.get("use_vastu")
        or structured.get("preferences", {}).get("vastu")
        or "vastu" in raw_lower
        or "vaastu" in raw_lower
    )

    inferred_candidates = list(REQUIRED_FIELDS)
    if structured.get("use_vastu"):
        inferred_candidates.append("plot_facing_direction")

    inferred_fields = [
        field for field in inferred_candidates if field not in explicit_fields
    ]
    structured["_inferred_fields"] = inferred_fields

    missing_fields = check_missing_fields(structured)
    clarification_questions = generate_clarification_questions(structured)

    structured["_missing_fields"] = missing_fields
    structured["_clarification_questions"] = clarification_questions

    parser_meta = {
        "ollama_status": ollama_status,
        "heuristic_fields": sorted(heuristic.keys()),
        "ollama_fields": sorted(ollama_data.keys()),
        "explicit_fields": sorted(explicit_fields),
        "inferred_fields": inferred_fields,
        "missing_fields": missing_fields,
        "clarification_questions": clarification_questions,
        "requires_clarification": bool(missing_fields),
    }

    return structured, parser_meta
