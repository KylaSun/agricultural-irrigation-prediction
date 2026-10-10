from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .schema import load_schema


WIRE_FIELDS = (
    "schema_version", "device_ms",
    "soil_1_raw", "soil_1_moisture_pct", "soil_1_status",
    "soil_2_raw", "soil_2_moisture_pct", "soil_2_status",
    "soil_3_raw", "soil_3_moisture_pct", "soil_3_status",
    "soil_4_raw", "soil_4_moisture_pct", "soil_4_status",
    "simulated",
)
WIRE_CONTRACT = load_schema()
WIRE_SCHEMA_VERSION = str(WIRE_CONTRACT["schema_version"])
STATUS_VALUES = frozenset(WIRE_CONTRACT["status_values"])
STATUS_FIELDS = tuple(f"soil_{index}_status" for index in range(1, 5))
INTEGER_FIELDS = tuple(f"soil_{index}_raw" for index in range(1, 5))
NUMBER_FIELDS = tuple(f"soil_{index}_moisture_pct" for index in range(1, 5))


class ParseError(ValueError):
    """A serial line is present but cannot be accepted as a data record."""


@dataclass(frozen=True)
class ParsedLine:
    values: dict[str, Any]
    warning: str | None = None


def parse_serial_line(raw: bytes | str) -> ParsedLine:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError("serial line is not valid UTF-8") from exc
    else:
        text = raw
    text = text.strip()
    if not text:
        raise ParseError("empty serial line")
    if text.startswith("#"):
        raise ParseError("debug line ignored")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"incomplete or invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ParseError("JSON record must be an object")
    missing_keys = [field for field in WIRE_FIELDS if field not in value]
    if missing_keys:
        raise ParseError(f"wrong field count/keys; missing: {', '.join(missing_keys)}")
    if len(value) != len(WIRE_FIELDS):
        extras = sorted(set(value) - set(WIRE_FIELDS))
        raise ParseError(f"wrong field count; unexpected: {', '.join(extras)}")
    if value["schema_version"] != WIRE_SCHEMA_VERSION:
        raise ParseError(
            f"unsupported schema_version: expected {WIRE_SCHEMA_VERSION}, "
            f"got {value['schema_version']!r}"
        )
    if isinstance(value["device_ms"], bool) or not isinstance(value["device_ms"], int):
        raise ParseError("device_ms must be an integer")
    if not 0 <= value["device_ms"] <= 4_294_967_295:
        raise ParseError("device_ms must be in range [0, 4294967295]")
    for field in INTEGER_FIELDS:
        item = value[field]
        if item is not None and (isinstance(item, bool) or not isinstance(item, int)):
            raise ParseError(f"{field} must be an integer or null")
    for field in NUMBER_FIELDS:
        item = value[field]
        if item is not None and (isinstance(item, bool) or not isinstance(item, (int, float))):
            raise ParseError(f"{field} must be numeric or null")
    for field in STATUS_FIELDS:
        if value[field] not in STATUS_VALUES:
            allowed = ", ".join(sorted(STATUS_VALUES))
            raise ParseError(f"{field} must be one of: {allowed}")
    if not isinstance(value["simulated"], bool):
        raise ParseError("simulated must be boolean")
    return ParsedLine(value)
