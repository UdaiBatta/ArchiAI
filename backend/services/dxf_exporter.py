"""DXF export helpers for layout zones."""

from __future__ import annotations

import io
from typing import Iterable

import ezdxf


def export_zones_to_dxf(zones: Iterable[dict]) -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    for zone in zones:
        x = float(zone.get("x", 0.0) or 0.0)
        y = float(zone.get("y", 0.0) or 0.0)
        width = float(zone.get("width_m", 0.0) or 0.0)
        depth = float(zone.get("depth_m", 0.0) or 0.0)
        room_type = str(zone.get("room_type", "Zone") or "Zone")

        points = [
            (x, y),
            (x + width, y),
            (x + width, y + depth),
            (x, y + depth),
            (x, y),
        ]
        msp.add_lwpolyline(points, close=True)
        msp.add_text(room_type, dxfattribs={"insert": (x + width / 2.0, y + depth / 2.0), "height": 0.5})

    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")
