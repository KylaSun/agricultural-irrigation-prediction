from __future__ import annotations

import csv
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rlls_demo.csv_store import CSV_FIELDS


def update_composite(record: dict[str, object]) -> None:
    values = []
    for probe in range(1, 5):
        value = record.get(f"soil_{probe}_moisture_pct")
        status = record.get(f"soil_{probe}_status")
        if value is not None and status in {"ok", "simulated"} and 0 <= float(value) <= 100:
            values.append(float(value))
    record["soil_composite_count"] = len(values)
    record["soil_composite_pct"] = round(float(statistics.median(values)), 2) if len(values) >= 2 else None
    record["soil_composite_spread_pct"] = round(max(values) - min(values), 2) if len(values) >= 2 else None


def simulated_record(index: int, *, timestamp: datetime | None = None) -> dict[str, object]:
    observed = timestamp or datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc) + timedelta(seconds=index)
    record: dict[str, object] = {
        "timestamp_utc": observed.isoformat().replace("+00:00", "Z"),
        "device_ms": index * 1000,
        "weather_temp": 23.5,
        "weather_humidity": 64.0,
        "weather_rain": 0.0,
        "weather_pressure": 1012.0,
        "weather_wind_speed": 9.2,
        "weather_radiation": 410.0,
        "active_probe": "soil_1",
        "simulated": True,
        "mode": "c2_low_cost_hybrid",
        "quality_flag": "simulated",
        "quality_detail": "SIMULATED_DATA",
    }
    for probe, offset in enumerate((-3.0, -1.0, 1.5, 3.5), start=1):
        pct = round(49.0 + offset + 2.0 * math.sin(index / 7 + probe * 0.15), 2)
        record[f"soil_{probe}_raw"] = 3200 - int(pct * 18)
        record[f"soil_{probe}_moisture_pct"] = pct
        record[f"soil_{probe}_status"] = "simulated"
    update_composite(record)
    record["soil_moisture"] = record["soil_1_moisture_pct"]
    return record


def write(name: str, records: list[dict[str, object]]) -> None:
    path = PROJECT_ROOT / "data" / "replay" / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({field: record.get(field) for field in CSV_FIELDS} for record in records)


def main() -> None:
    normal = [simulated_record(index) for index in range(30)]
    write("simulated_normal.csv", normal)

    missing = simulated_record(0)
    missing.update({
        "active_probe": "soil_2",
        "soil_2_raw": None,
        "soil_2_moisture_pct": None,
        "soil_2_status": "read_error",
        "soil_moisture": None,
        "quality_flag": "missing",
        "quality_detail": "SIMULATED_DATA; soil_2_status: read_error",
    })
    update_composite(missing)
    write("simulated_missing.csv", [missing])

    out_of_range = simulated_record(0)
    out_of_range.update({
        "active_probe": "soil_3",
        "soil_3_raw": 5000,
        "soil_3_moisture_pct": 120.0,
        "soil_3_status": "out_of_range",
        "soil_moisture": None,
        "quality_flag": "out_of_range",
        "quality_detail": "SIMULATED_DATA; soil_3_raw and soil_3_moisture_pct out_of_range",
    })
    update_composite(out_of_range)
    write("simulated_out_of_range.csv", [out_of_range])

    stale = simulated_record(0, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc))
    stale.update({"quality_flag": "stale", "quality_detail": "SIMULATED_DATA; STALE_FIXTURE"})
    write("simulated_stale.csv", [stale])

    modes = []
    for index, mode in enumerate(("c1_soil_only", "c2_low_cost_hybrid", "c3_sensor_rich")):
        record = simulated_record(index)
        record["mode"] = mode
        modes.append(record)
    write("simulated_modes.csv", modes)


if __name__ == "__main__":
    main()
