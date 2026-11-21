"""Build small DXF files in memory for tests."""

from __future__ import annotations

import io

import ezdxf


def new_doc(units: int = 4):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = units
    return doc


def rect(msp, x, y, w, h, layer="0"):
    msp.add_lwpolyline(
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": layer}
    )


def to_bytes(doc) -> bytes:
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")
