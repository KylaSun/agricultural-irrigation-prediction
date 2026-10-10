from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


CSV_FIELDS = [
    "timestamp_utc", "device_ms",
    "soil_1_raw", "soil_1_moisture_pct", "soil_1_status",
    "soil_2_raw", "soil_2_moisture_pct", "soil_2_status",
    "soil_3_raw", "soil_3_moisture_pct", "soil_3_status",
    "soil_4_raw", "soil_4_moisture_pct", "soil_4_status",
    "soil_composite_pct", "soil_composite_count", "soil_composite_spread_pct",
    "weather_temp", "weather_humidity",
    "weather_rain", "weather_pressure", "weather_wind_speed", "weather_radiation",
    "soil_temperature_0-7cm", "soil_temperature_7-18cm", "ec", "ph", "water_vol_past_4h",
    "active_probe", "soil_moisture", "simulated", "mode", "quality_flag", "quality_detail",
]


def append_csv(path: str | Path, record: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not destination.exists() or destination.stat().st_size == 0
    with destination.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        writer.writerow({key: record.get(key) for key in CSV_FIELDS})


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
