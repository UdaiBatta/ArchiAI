"""
services/rule_engine.py — Deterministic Building Compliance Engine
===================================================================

PURPOSE:
    This is the HEART of Archi3D's compliance system. It takes a building
    design (plot dimensions, floors, units) and a BylawRuleset, and
    deterministically checks whether the design is legal.

    CRITICAL DESIGN PRINCIPLE:
    ★ The LLM (Ollama) is NEVER used here. ★
    All calculations are pure math. This makes the system:
      - Auditable (you can trace every number)
      - Reproducible (same input → same output, always)
      - Legally defensible (no AI "hallucinations" in compliance checks)

HOW IT WORKS (step by step):
    1. calculate_buildable_area()
       → Subtracts setbacks from plot dimensions
       → Returns the actual area you can legally build on

    2. calculate_total_built_area()
       → buildable_footprint × number_of_floors
       → Total area if you build to the maximum footprint on every floor

    3. validate_far()
       → Checks if total_built_area / plot_area ≤ max_far
       → FAR = Floor Area Ratio (also called FSI in India)

    4. validate_floor_count()
       → Checks if requested floors ≤ max_floors from bylaws

    5. validate_height()
       → Checks if (floors × floor_height) ≤ max_height_m

    6. validate_plot_coverage()
       → Checks if buildable_footprint / plot_area ≤ max_plot_coverage_pct

    7. calculate_parking_requirement()
       → Returns how many stalls are needed

    8. run_full_compliance() — Main entry point
       → Runs ALL checks and returns a ComplianceReport

KEY CONCEPTS:
    FAR (Floor Area Ratio) / FSI (Floor Space Index):
        FAR = Total Built-Up Area ÷ Plot Area
        If plot = 1200 sq.m and FAR limit = 1.5:
          Maximum total built area = 1200 × 1.5 = 1800 sq.m

    Setbacks:
        The mandated empty space between your building and the plot boundary.
        Setback reduces your usable building footprint:
          Buildable Width = Plot Width − setback_side − setback_side
          Buildable Depth = Plot Depth − setback_front − setback_rear

    Plot Coverage:
        The percentage of your plot occupied by the building footprint
        (footprint = the ground floor area, seen from above).
        Coverage = Building Footprint ÷ Plot Area × 100

USAGE EXAMPLE:
    from services.bylaw_loader import load_bylaws
    from services.rule_engine import run_full_compliance

    bylaws = load_bylaws("india_mumbai", "residential")
    report = run_full_compliance(
        plot_width_m=30.0,
        plot_depth_m=40.0,
        num_floors=3,
        num_units=1,
        bylaws=bylaws
    )
    print(report.is_fully_compliant)   # True or False
    print(report.summary())            # Human-readable summary

DEBUGGING:
    - Each ComplianceCheck has .passed, .actual_value, .limit_value
    - iterate report.checks to see which specific check failed
    - Use report.adjusted_floors to see if floors were auto-reduced
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

from services.bylaw_loader import BylawRuleset


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class BuildableArea:
    """
    Represents the usable area after applying setbacks.

    All values in metres (m) or square metres (sq.m).

    FIELDS:
      plot_width_m       → Original plot width (as given by user)
      plot_depth_m       → Original plot depth (as given by user)
      plot_area_sqm      → Total plot area = width × depth
      buildable_width_m  → Width after removing both side setbacks
                           = plot_width − 2 × setback_side
      buildable_depth_m  → Depth after removing front + rear setbacks
                           = plot_depth − setback_front − setback_rear
      buildable_area_sqm → Area you can legally build on per floor
                           = buildable_width × buildable_depth
      setback_front_m    → Setback applied at the front (road-facing side)
      setback_rear_m     → Setback applied at the rear
      setback_side_m     → Setback applied on each side

    EXAMPLE (Mumbai, 30×40 plot with 3m front/rear, 1.5m sides):
      buildable_width_m  = 30 − (1.5 + 1.5) = 27.0 m
      buildable_depth_m  = 40 − (3 + 3)     = 34.0 m
      buildable_area_sqm = 27.0 × 34.0      = 918.0 sq.m
    """
    plot_width_m: float
    plot_depth_m: float
    plot_area_sqm: float
    buildable_width_m: float
    buildable_depth_m: float
    buildable_area_sqm: float
    setback_front_m: float
    setback_rear_m: float
    setback_side_m: float

    def to_dict(self) -> dict:
        return {
            "plot_width_m": round(self.plot_width_m, 2),
            "plot_depth_m": round(self.plot_depth_m, 2),
            "plot_area_sqm": round(self.plot_area_sqm, 2),
            "buildable_width_m": round(self.buildable_width_m, 2),
            "buildable_depth_m": round(self.buildable_depth_m, 2),
            "buildable_area_sqm": round(self.buildable_area_sqm, 2),
            "setback_front_m": round(self.setback_front_m, 2),
            "setback_rear_m": round(self.setback_rear_m, 2),
            "setback_side_m": round(self.setback_side_m, 2),
        }


@dataclass
class ComplianceCheck:
    """
    Result of a single compliance check (one rule, one test).

    FIELDS:
      check_name    → Short name for this check, e.g., "FAR / FSI Limit"
      passed        → True if the design meets this rule, False if it violates it
      actual_value  → The value from the design (e.g., the actual FAR achieved)
      limit_value   → The maximum/minimum value allowed by the bylaw
      unit          → The unit of the values (e.g., "sq.m", "floors", "m", "%")
      message       → Human-readable explanation of the result
      severity      → "error" (blocking violation) or "warning" (advisory)

    EXAMPLE (FAR check failed):
      ComplianceCheck(
          check_name="FAR / FSI Limit",
          passed=False,
          actual_value=2.1,
          limit_value=1.5,
          unit="ratio",
          message="FAR of 2.10 exceeds the maximum allowed FAR of 1.50.",
          severity="error"
      )
    """
    check_name: str
    passed: bool
    actual_value: float
    limit_value: float
    unit: str
    message: str
    severity: str = "error"  # "error" or "warning"

    def to_dict(self) -> dict:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "actual_value": round(self.actual_value, 3),
            "limit_value": round(self.limit_value, 3),
            "unit": self.unit,
            "message": self.message,
            "severity": self.severity,
            "status": "✅ PASS" if self.passed else ("⚠️ WARNING" if self.severity == "warning" else "❌ FAIL"),
        }


@dataclass
class ComplianceReport:
    """
    Full compliance report for a building design against a bylaw ruleset.

    This is the main output of run_full_compliance().

    FIELDS:
      region_id              → Which bylaw region was applied
      region_name            → Human-readable region name
      building_type          → "residential" or "commercial"
      is_fully_compliant     → True only if ALL error-severity checks passed
                               (warnings don't affect this flag)
      buildable_area         → The computed buildable area (see BuildableArea)
      checks                 → List of all individual compliance checks
      total_built_area_sqm   → Total built area across all requested floors
                               = buildable_area × num_floors
      actual_far             → The FAR the design actually achieves
                               = total_built_area / plot_area
      required_parking_stalls → Number of parking stalls required by bylaw
      adjusted_floors        → The max legal floors (may be < num_floors if over limit)
      notes                  → Extra notes from the rule engine

    USAGE:
      for check in report.checks:
          if not check.passed:
              print(f"VIOLATION: {check.message}")
    """
    region_id: str
    region_name: str
    building_type: str
    is_fully_compliant: bool
    buildable_area: BuildableArea
    checks: List[ComplianceCheck]
    total_built_area_sqm: float
    actual_far: float
    required_parking_stalls: int
    adjusted_floors: int
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """
        Return a plain-English summary of the compliance result.

        EXAMPLE OUTPUT:
          ✅ Design is FULLY COMPLIANT with India — Mumbai (DCPR 2034).
             • Buildable area per floor: 918.0 sq.m
             • Total built area (3 floors): 2754.0 sq.m
             • Actual FAR: 1.15 (limit: 1.5) ✅
             • Parking required: 1 stall(s)
        """
        status = "✅ FULLY COMPLIANT" if self.is_fully_compliant else "❌ NOT COMPLIANT"
        lines = [
            f"{status} with {self.region_name}",
            f"  Building type: {self.building_type}",
            f"  Buildable area/floor: {self.buildable_area.buildable_area_sqm:.1f} sq.m",
            f"  Total built area ({self.adjusted_floors} floors): {self.total_built_area_sqm:.1f} sq.m",
            f"  Actual FAR: {self.actual_far:.2f} (limit: {self.buildable_area.setback_front_m:.1f})",
            f"  Parking required: {self.required_parking_stalls} stall(s)",
        ]
        for check in self.checks:
            status_icon = "✅" if check.passed else ("⚠️" if check.severity == "warning" else "❌")
            lines.append(f"  {status_icon} {check.check_name}: {check.message}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "region_id": self.region_id,
            "region_name": self.region_name,
            "building_type": self.building_type,
            "is_fully_compliant": self.is_fully_compliant,
            "buildable_area": self.buildable_area.to_dict(),
            "checks": [c.to_dict() for c in self.checks],
            "total_built_area_sqm": round(self.total_built_area_sqm, 2),
            "actual_far": round(self.actual_far, 3),
            "required_parking_stalls": self.required_parking_stalls,
            "adjusted_floors": self.adjusted_floors,
            "notes": self.notes,
        }


# ── Core Calculation Functions ─────────────────────────────────────────────────
# Each function does ONE thing and is independently testable.

def calculate_buildable_area(
    plot_width_m: float,
    plot_depth_m: float,
    bylaws: BylawRuleset,
) -> BuildableArea:
    """
    Calculate the usable building footprint after applying required setbacks.

    FORMULA:
      buildable_width = plot_width − (setback_side × 2)
      buildable_depth = plot_depth − setback_front − setback_rear
      buildable_area  = buildable_width × buildable_depth

    NOTE:
      If the setbacks consume the entire plot (negative buildable area),
      buildable_width and buildable_depth are clamped to 0.
      This would mean the plot is too small for the required setbacks.

    Args:
        plot_width_m: Total plot width in metres (e.g., 30.0)
        plot_depth_m: Total plot depth in metres (e.g., 40.0)
        bylaws:       The BylawRuleset to apply

    Returns:
        BuildableArea dataclass with all computed values

    Example (Mumbai, 30×40, 3m front/rear, 1.5m side):
        buildable_width = 30 − 3.0  = 27.0 m
        buildable_depth = 40 − 6.0  = 34.0 m
        buildable_area  = 27 × 34   = 918.0 sq.m
    """
    plot_area = plot_width_m * plot_depth_m

    # Apply setbacks — clamp to 0 if setbacks exceed plot dimensions
    buildable_width = max(0.0, plot_width_m - (bylaws.setback_side_m * 2))
    buildable_depth = max(0.0, plot_depth_m - bylaws.setback_front_m - bylaws.setback_rear_m)
    buildable_area = buildable_width * buildable_depth

    return BuildableArea(
        plot_width_m=plot_width_m,
        plot_depth_m=plot_depth_m,
        plot_area_sqm=plot_area,
        buildable_width_m=buildable_width,
        buildable_depth_m=buildable_depth,
        buildable_area_sqm=buildable_area,
        setback_front_m=bylaws.setback_front_m,
        setback_rear_m=bylaws.setback_rear_m,
        setback_side_m=bylaws.setback_side_m,
    )


def validate_buildable_area(buildable_area: BuildableArea) -> ComplianceCheck:
    """
    Check that there IS a usable buildable area (plot isn't consumed by setbacks).

    A plot is valid if both buildable_width and buildable_depth are > 0.
    In practice, this check fails only for very small plots with large setbacks.
    """
    has_area = (
        buildable_area.buildable_width_m > 0
        and buildable_area.buildable_depth_m > 0
    )
    if has_area:
        msg = (
            f"Buildable area is {buildable_area.buildable_area_sqm:.1f} sq.m "
            f"({buildable_area.buildable_width_m:.1f}m × {buildable_area.buildable_depth_m:.1f}m). "
            f"Setbacks applied: front {buildable_area.setback_front_m}m, "
            f"rear {buildable_area.setback_rear_m}m, side {buildable_area.setback_side_m}m each."
        )
    else:
        msg = (
            f"Plot ({buildable_area.plot_width_m}m × {buildable_area.plot_depth_m}m) is too small "
            f"for the required setbacks (front {buildable_area.setback_front_m}m, "
            f"rear {buildable_area.setback_rear_m}m, side {buildable_area.setback_side_m}m). "
            f"No buildable area remains."
        )
    return ComplianceCheck(
        check_name="Buildable Area",
        passed=has_area,
        actual_value=buildable_area.buildable_area_sqm,
        limit_value=0.0,
        unit="sq.m",
        message=msg,
        severity="error",
    )


def validate_floor_count(
    num_floors: int,
    bylaws: BylawRuleset,
) -> tuple[ComplianceCheck, int]:
    """
    Check if the requested number of floors is within the bylaw limit.

    Returns:
        (ComplianceCheck, adjusted_floors)
        adjusted_floors = min(num_floors, bylaws.max_floors)
        The layout generator will use adjusted_floors for calculations.

    Example:
        validate_floor_count(5, bylaws_with_max_4)
        → ComplianceCheck(passed=False, ...), adjusted_floors=4
    """
    adjusted = min(num_floors, bylaws.max_floors)
    passed = num_floors <= bylaws.max_floors

    if passed:
        msg = (
            f"Requested {num_floors} floor(s) is within the maximum of "
            f"{bylaws.max_floors} floor(s) allowed."
        )
    else:
        msg = (
            f"Requested {num_floors} floor(s) EXCEEDS the maximum of "
            f"{bylaws.max_floors} floor(s). "
            f"Design will be adjusted to {adjusted} floor(s)."
        )
    return (
        ComplianceCheck(
            check_name="Floor Count Limit",
            passed=passed,
            actual_value=float(num_floors),
            limit_value=float(bylaws.max_floors),
            unit="floors",
            message=msg,
            severity="error",
        ),
        adjusted,
    )


def validate_height(
    num_floors: int,
    bylaws: BylawRuleset,
) -> ComplianceCheck:
    """
    Check if the total building height is within the bylaw maximum.

    Height is estimated as:  num_floors × floor_height_m
    (We use the standard floor height from the bylaw file, typically 3.0m.)

    This is an estimate — actual height depends on slab thickness, parapet,
    roof water tank, etc. The layout generator will refine this in Phase 3.
    """
    estimated_height = num_floors * bylaws.floor_height_m
    passed = estimated_height <= bylaws.max_height_m

    if passed:
        msg = (
            f"Estimated height of {estimated_height:.1f}m ({num_floors} floors × "
            f"{bylaws.floor_height_m}m) is within the {bylaws.max_height_m}m limit."
        )
    else:
        msg = (
            f"Estimated height of {estimated_height:.1f}m ({num_floors} floors × "
            f"{bylaws.floor_height_m}m) EXCEEDS the maximum height of {bylaws.max_height_m}m."
        )
    return ComplianceCheck(
        check_name="Height Limit",
        passed=passed,
        actual_value=estimated_height,
        limit_value=bylaws.max_height_m,
        unit="m",
        message=msg,
        severity="error",
    )


def validate_far(
    buildable_area: BuildableArea,
    num_floors: int,
    bylaws: BylawRuleset,
) -> tuple[ComplianceCheck, float, float]:
    """
    Check if the total built area respects the FAR (Floor Area Ratio) limit.

    FORMULA:
      total_built_area = buildable_footprint × num_floors
      actual_far       = total_built_area ÷ plot_area
      passed           = actual_far ≤ max_far

    Note: This uses the FULL buildable footprint × floors as a worst-case.
    In reality, not every floor will be fully built out. The layout generator
    in Phase 3 will produce a more accurate built area estimate.

    Returns:
        (ComplianceCheck, total_built_area_sqm, actual_far)
    """
    total_built_area = buildable_area.buildable_area_sqm * num_floors
    actual_far = total_built_area / buildable_area.plot_area_sqm if buildable_area.plot_area_sqm > 0 else 0.0
    max_allowed_area = buildable_area.plot_area_sqm * bylaws.max_far
    passed = actual_far <= bylaws.max_far

    if passed:
        msg = (
            f"FAR of {actual_far:.2f} (total built area {total_built_area:.1f} sq.m ÷ "
            f"plot area {buildable_area.plot_area_sqm:.1f} sq.m) is within "
            f"the maximum FAR of {bylaws.max_far}. "
            f"Maximum allowable built area: {max_allowed_area:.1f} sq.m."
        )
    else:
        msg = (
            f"FAR of {actual_far:.2f} (total built area {total_built_area:.1f} sq.m ÷ "
            f"plot area {buildable_area.plot_area_sqm:.1f} sq.m) EXCEEDS "
            f"the maximum FAR of {bylaws.max_far}. "
            f"Maximum allowable built area: {max_allowed_area:.1f} sq.m. "
            f"Reduce floors or plot footprint."
        )
    return (
        ComplianceCheck(
            check_name="FAR / FSI Limit",
            passed=passed,
            actual_value=actual_far,
            limit_value=bylaws.max_far,
            unit="ratio",
            message=msg,
            severity="error",
        ),
        total_built_area,
        actual_far,
    )


def validate_plot_coverage(
    buildable_area: BuildableArea,
    bylaws: BylawRuleset,
) -> ComplianceCheck:
    """
    Check if the building footprint coverage respects the plot coverage limit.

    FORMULA:
      actual_coverage_pct = buildable_footprint ÷ plot_area × 100

    Note: We check the full buildable footprint as the worst case.
    Phase 3 layout will optimise the actual footprint used.
    """
    actual_coverage = (
        (buildable_area.buildable_area_sqm / buildable_area.plot_area_sqm * 100)
        if buildable_area.plot_area_sqm > 0 else 0.0
    )
    passed = actual_coverage <= bylaws.max_plot_coverage_pct

    if passed:
        msg = (
            f"Plot coverage of {actual_coverage:.1f}% (footprint {buildable_area.buildable_area_sqm:.1f} sq.m ÷ "
            f"plot {buildable_area.plot_area_sqm:.1f} sq.m) is within the "
            f"{bylaws.max_plot_coverage_pct:.0f}% limit."
        )
    else:
        msg = (
            f"Plot coverage of {actual_coverage:.1f}% EXCEEDS the maximum "
            f"of {bylaws.max_plot_coverage_pct:.0f}%. "
            f"Building footprint must be reduced."
        )
    return ComplianceCheck(
        check_name="Plot Coverage Limit",
        passed=passed,
        actual_value=actual_coverage,
        limit_value=bylaws.max_plot_coverage_pct,
        unit="%",
        message=msg,
        severity="error",
    )


def calculate_parking_requirement(
    num_units: int,
    bylaws: BylawRuleset,
) -> tuple[int, ComplianceCheck]:
    """
    Calculate the number of parking stalls required by the bylaw.

    FORMULA:
      required_stalls = ceil(num_units × min_stalls_per_unit)

    We use math.ceil to always round UP — you can't have half a parking stall.

    Args:
        num_units: Number of residential units (or 100 sq.m blocks for commercial)
        bylaws:    BylawRuleset containing parking rules

    Returns:
        (required_stalls: int, ComplianceCheck)

    Example (Mumbai, 1 unit):
        required_stalls = ceil(1 × 1.0) = 1 stall
    """
    required = math.ceil(num_units * bylaws.parking.min_stalls_per_unit)

    msg = (
        f"{required} parking stall(s) required for {num_units} unit(s) "
        f"({bylaws.parking.min_stalls_per_unit} stall/unit per {bylaws.region_name}). "
        f"Each stall: {bylaws.parking.stall_width_m}m × {bylaws.parking.stall_depth_m}m "
        f"with {bylaws.parking.aisle_width_m}m aisle."
    )
    if bylaws.parking.notes:
        msg += f" Note: {bylaws.parking.notes}"

    return required, ComplianceCheck(
        check_name="Parking Requirement",
        passed=True,   # This is always "advisory" — tells you what's needed
        actual_value=float(required),
        limit_value=bylaws.parking.min_stalls_per_unit * num_units,
        unit="stalls",
        message=msg,
        severity="warning",  # Warning only — not a blocking rule
    )


# ── Main Orchestrator ──────────────────────────────────────────────────────────

def run_full_compliance(
    plot_width_m: float,
    plot_depth_m: float,
    num_floors: int,
    num_units: int,
    bylaws: BylawRuleset,
) -> ComplianceReport:
    """
    Run ALL compliance checks and return a complete ComplianceReport.

    This is the MAIN ENTRY POINT for the rule engine.
    The Django view (apps/design/views.py) calls this function.

    CHECKS PERFORMED (in order):
      1. Buildable area  — is there any area left after setbacks?
      2. Floor count     — do we exceed max_floors?
      3. Height          — does height exceed max_height_m?
      4. FAR / FSI       — does total built area / plot area exceed max_far?
      5. Plot coverage   — does footprint exceed max_plot_coverage_pct?
      6. Parking         — how many stalls are required? (advisory)

    Args:
        plot_width_m:  Width of the plot in metres
        plot_depth_m:  Depth of the plot in metres
        num_floors:    Number of floors requested by the user
        num_units:     Number of residential units (1 for individual house)
        bylaws:        BylawRuleset loaded by bylaw_loader.load_bylaws()

    Returns:
        ComplianceReport with all check results, adjustments, and summary.

    DEBUGGING:
        report = run_full_compliance(...)
        for c in report.checks:
            print(f"{'✅' if c.passed else '❌'} {c.check_name}: {c.message}")
    """
    checks: List[ComplianceCheck] = []
    notes: List[str] = []

    # ── Step 1: Buildable Area ─────────────────────────────────────────────────
    buildable = calculate_buildable_area(plot_width_m, plot_depth_m, bylaws)
    area_check = validate_buildable_area(buildable)
    checks.append(area_check)

    if not area_check.passed:
        # No point running further checks if there's no buildable area
        notes.append("Plot is too small for required setbacks. All further checks skipped.")
        return ComplianceReport(
            region_id=bylaws.region_id,
            region_name=bylaws.region_name,
            building_type=bylaws.building_type,
            is_fully_compliant=False,
            buildable_area=buildable,
            checks=checks,
            total_built_area_sqm=0.0,
            actual_far=0.0,
            required_parking_stalls=0,
            adjusted_floors=0,
            notes=notes,
        )

    # ── Step 2: Floor Count ────────────────────────────────────────────────────
    floor_check, adjusted_floors = validate_floor_count(num_floors, bylaws)
    checks.append(floor_check)
    if not floor_check.passed:
        notes.append(f"Floor count reduced from {num_floors} to {adjusted_floors} to meet bylaw limit.")

    # ── Step 3: Height ─────────────────────────────────────────────────────────
    height_check = validate_height(adjusted_floors, bylaws)
    checks.append(height_check)

    # ── Step 4: FAR / FSI ──────────────────────────────────────────────────────
    far_check, total_built_area, actual_far = validate_far(buildable, adjusted_floors, bylaws)
    checks.append(far_check)

    # If FAR is violated, calculate the max floors that would be compliant
    if not far_check.passed:
        max_compliant_floors = math.floor(
            (bylaws.max_far * buildable.plot_area_sqm) / buildable.buildable_area_sqm
        )
        max_compliant_floors = max(1, max_compliant_floors)
        adjusted_floors = min(adjusted_floors, max_compliant_floors)
        total_built_area = buildable.buildable_area_sqm * adjusted_floors
        actual_far = total_built_area / buildable.plot_area_sqm
        notes.append(
            f"FAR limit requires reducing to {adjusted_floors} floor(s). "
            f"Adjusted total built area: {total_built_area:.1f} sq.m (FAR: {actual_far:.2f})."
        )

    # ── Step 5: Plot Coverage ──────────────────────────────────────────────────
    coverage_check = validate_plot_coverage(buildable, bylaws)
    checks.append(coverage_check)
    if not coverage_check.passed:
        notes.append(
            f"Plot coverage of {coverage_check.actual_value:.1f}% exceeds limit. "
            "Building footprint must be reduced. Consider reducing plot usage or increasing setbacks."
        )

    # ── Step 6: Parking Requirement ────────────────────────────────────────────
    required_stalls, parking_check = calculate_parking_requirement(num_units, bylaws)
    checks.append(parking_check)

    # ── Final Verdict ──────────────────────────────────────────────────────────
    # is_fully_compliant = True only if ALL error-severity checks passed
    is_compliant = all(
        check.passed for check in checks if check.severity == "error"
    )
    if bylaws.notes:
        notes.append(f"Bylaw notes: {bylaws.notes}")

    return ComplianceReport(
        region_id=bylaws.region_id,
        region_name=bylaws.region_name,
        building_type=bylaws.building_type,
        is_fully_compliant=is_compliant,
        buildable_area=buildable,
        checks=checks,
        total_built_area_sqm=round(total_built_area, 2),
        actual_far=round(actual_far, 3),
        required_parking_stalls=required_stalls,
        adjusted_floors=adjusted_floors,
        notes=notes,
    )
