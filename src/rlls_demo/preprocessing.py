from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any, Mapping

from .schema import feature_order, load_modes, load_schema


NUMERIC_TYPES = {"number", "integer"}
QUALITY_PRIORITY = {"invalid": 6, "out_of_range": 5, "stale": 4, "missing": 3, "simulated": 2, "valid": 1}


@dataclass(frozen=True)
class ProcessedRecord:
    record: dict[str, Any]
    features: dict[str, Any]
    quality_flag: str
    issues: tuple[str, ...]


class MissingValueStrategy:
    """Configurable hook. Production strategy must match model training."""

    name = "passthrough"

    def apply(self, features: dict[str, Any]) -> dict[str, Any]:
        return features


class ErrorOnMissing(MissingValueStrategy):
    name = "error"

    def apply(self, features: dict[str, Any]) -> dict[str, Any]:
        missing = [key for key, value in features.items() if value is None]
        if missing:
            raise ValueError(f"Missing required model features: {', '.join(missing)}")
        return features


class ConstantFill(MissingValueStrategy):
    name = "constant"

    def __init__(self, values: Mapping[str, float]):
        self.values = dict(values)

    def apply(self, features: dict[str, Any]) -> dict[str, Any]:
        result = dict(features)
        for key, value in result.items():
            if value is None and key in self.values:
                result[key] = self.values[key]
        return result


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def _coerce(value: Any, field_type: str) -> Any:
    if value is None or value == "":
        return None
    if field_type == "number":
        if isinstance(value, bool):
            raise ValueError("boolean is not numeric")
        return float(value)
    if field_type == "integer":
        if isinstance(value, bool):
            raise ValueError("boolean is not integer")
        converted = float(value)
        if not converted.is_integer():
            raise ValueError("non-integral value")
        return int(converted)
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
        raise ValueError("not a boolean")
    return str(value)


def process_record(
    raw: Mapping[str, Any],
    mode: str,
    *,
    active_probe: str = "soil_1",
    now: datetime | None = None,
    stale_after_seconds: int = 10,
    disabled_fields: set[str] | None = None,
    missing_strategy: MissingValueStrategy | None = None,
) -> ProcessedRecord:
    schema = load_schema()
    modes = load_modes()
    order = feature_order(mode, modes)
    record = dict(raw)
    issues: list[str] = []
    states: list[str] = []
    disabled = disabled_fields or set()
    allowed_probes = {f"soil_{index}" for index in range(1, 5)} | {"soil_composite"}
    if active_probe not in allowed_probes:
        raise ValueError(f"Unknown active_probe: {active_probe}")
    record["active_probe"] = active_probe
    record["soil_moisture"] = None

    existing_flag = str(raw.get("quality_flag", "")).lower()
    if existing_flag in QUALITY_PRIORITY and existing_flag != "valid":
        states.append(existing_flag)
    existing_detail = str(raw.get("quality_detail") or "").strip()
    if existing_detail:
        issues.append(existing_detail)

    for field, definition in schema["fields"].items():
        if field not in record:
            record[field] = None
        if definition["type"] in NUMERIC_TYPES or definition["type"] == "boolean":
            try:
                record[field] = _coerce(record[field], definition["type"])
            except (TypeError, ValueError) as exc:
                record[field] = None
                states.append("invalid")
                issues.append(f"{field}: type conversion failed ({exc})")
        value = record[field]
        bounds = definition.get("range")
        if value is not None and definition["type"] in NUMERIC_TYPES and isinstance(bounds, list) and len(bounds) == 2:
            if value < bounds[0] or value > bounds[1]:
                record[field] = None
                states.append("out_of_range")
                issues.append(f"{field}: out_of_range [{bounds[0]}, {bounds[1]}]")

    for field in disabled:
        if field in record:
            record[field] = None
            issues.append(f"{field}: disabled")

    sensor_groups = {
        f"soil_{index}_status": (f"soil_{index}_raw", f"soil_{index}_moisture_pct")
        for index in range(1, 5)
    }
    for status_field, affected in sensor_groups.items():
        status = str(raw.get(status_field, "")).lower()
        if status in {"disabled", "timeout", "read_error", "out_of_range", "stale"}:
            state = "missing" if status in {"disabled", "timeout", "read_error"} else status
            states.append(state)
            issues.append(f"{status_field}: {status}")
            if status != "stale":
                for field in affected:
                    record[field] = None
        elif status == "simulated":
            states.append("simulated")

    # Build a robust, auditable four-position summary after all range, status and
    # switch checks. Missing values are excluded rather than treated as zero.
    valid_probe_values = [
        float(record[f"soil_{index}_moisture_pct"])
        for index in range(1, 5)
        if record.get(f"soil_{index}_moisture_pct") is not None
    ]
    record["soil_composite_count"] = len(valid_probe_values)
    record["soil_composite_spread_pct"] = (
        round(max(valid_probe_values) - min(valid_probe_values), 2)
        if len(valid_probe_values) >= 2
        else None
    )
    record["soil_composite_pct"] = (
        round(float(median(valid_probe_values)), 2)
        if len(valid_probe_values) >= 2
        else None
    )

    # C1/C2/C3 still receive exactly one canonical soil_moisture feature.
    # It may come from one selected position or the explicit derived composite.
    if active_probe == "soil_composite":
        record["soil_moisture"] = record["soil_composite_pct"]
        if record["soil_moisture"] is None:
            states.append("missing")
            issues.append("soil_composite: fewer than 2 valid probes")
    else:
        record["soil_moisture"] = record.get(f"{active_probe}_moisture_pct")

    try:
        observed = _utc(record.get("timestamp_utc"))
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        age = (current - observed).total_seconds()
        if age > stale_after_seconds:
            states.append("stale")
            issues.append(f"timestamp_utc: stale by {int(age)}s")
    except (TypeError, ValueError):
        states.append("invalid")
        issues.append("timestamp_utc: invalid or missing")

    features = {field: record.get(field) for field in order}
    if any(value is None for value in features.values()):
        states.append("missing")
    if str(record.get("quality_flag", "")).lower() == "simulated" or raw.get("simulated") is True:
        states.append("simulated")
        if "SIMULATED_DATA" not in issues:
            issues.append("SIMULATED_DATA")
    strategy = missing_strategy or MissingValueStrategy()
    features = strategy.apply(features)
    flag = max(states or ["valid"], key=lambda state: QUALITY_PRIORITY[state])
    record["mode"] = mode
    record["quality_flag"] = flag
    record["quality_detail"] = "; ".join(issues)
    return ProcessedRecord(record, features, flag, tuple(issues))
