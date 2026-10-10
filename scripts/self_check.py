"""Dependency-light smoke checks for environments where pytest is not installed."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rlls_demo.csv_store import append_csv, read_csv
from rlls_demo.model_adapter import MockModelAdapter, ModelContractError
from rlls_demo.preprocessing import process_record
from rlls_demo.schema import feature_order
from rlls_demo.serial_parser import ParseError, parse_serial_line


def main() -> int:
    wire = {
        "schema_version": "2.0.0-demo", "device_ms": 1,
        "soil_1_raw": 2200, "soil_1_moisture_pct": 55.0, "soil_1_status": "ok",
        "soil_2_raw": 2250, "soil_2_moisture_pct": 52.0, "soil_2_status": "ok",
        "soil_3_raw": 2300, "soil_3_moisture_pct": 49.0, "soil_3_status": "ok",
        "soil_4_raw": 2350, "soil_4_moisture_pct": 46.0, "soil_4_status": "ok",
        "simulated": False,
    }
    assert parse_serial_line(json.dumps(wire)).values["device_ms"] == 1
    broken = dict(wire)
    del broken["soil_3_raw"]
    try:
        parse_serial_line(json.dumps(broken))
        raise AssertionError("wrong field count was accepted")
    except ParseError:
        pass

    record = {
        **wire, "timestamp_utc": "2026-10-08T04:00:00Z", "weather_temp": 23,
        "weather_humidity": 64, "weather_rain": 0, "weather_pressure": 1012,
        "weather_wind_speed": 9, "weather_radiation": 410,
        "mode": "c2_low_cost_hybrid", "quality_flag": "valid", "quality_detail": "",
    }
    checked = process_record(record, "c2_low_cost_hybrid", now=datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc))
    assert list(checked.features) == feature_order("c2_low_cost_hybrid")
    missing = process_record({**record, "soil_1_moisture_pct": None}, "c1_soil_only", now=datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc))
    assert missing.features["soil_moisture"] is None
    assert missing.features["soil_moisture"] != 0
    assert "soil_moisture" not in feature_order("weather_only")

    adapter = MockModelAdapter(["weather_temp", "weather_rain"])
    assert adapter.predict({"weather_temp": 23, "weather_rain": 0}).is_mock
    try:
        adapter.predict({"weather_temp": 23})
        raise AssertionError("missing model key was accepted")
    except ModelContractError:
        pass

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "roundtrip.csv"
        append_csv(path, {"timestamp_utc": "2026-10-08T04:00:00Z", "device_ms": 1, "soil_1_raw": None, "soil_1_moisture_pct": 0})
        row = read_csv(path)[0]
        assert row["soil_1_raw"] == "" and row["soil_1_moisture_pct"] == "0"

    print("self-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
