import csv
from datetime import datetime, timezone

import pytest

from rlls_demo.flash_log import parse_flash_payload, write_offline_csv, write_raw_jsonl
from scripts.validate_csv_contract import validate


RECORD = (
    '{"schema_version":"2.0.0-demo","device_ms":60000,'
    '"soil_1_raw":1900,"soil_1_moisture_pct":0.37,"soil_1_status":"ok",'
    '"soil_2_raw":900,"soil_2_moisture_pct":6.15,"soil_2_status":"ok",'
    '"soil_3_raw":400,"soil_3_moisture_pct":1.96,"soil_3_status":"ok",'
    '"soil_4_raw":700,"soil_4_moisture_pct":5.41,"soil_4_status":"ok",'
    '"simulated":false}'
)


def test_flash_dump_preserves_boot_segment_and_unknown_utc(tmp_path):
    payload = ["#RLLS_BOOT id=abc123 clock=unsynced", RECORD]
    records = parse_flash_payload(payload)
    assert records[0].boot_id == "abc123"
    assert records[0].values["device_ms"] == 60000

    destination = tmp_path / "offline.csv"
    write_offline_csv(
        destination,
        records,
        downloaded_at=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc),
    )
    with destination.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["timestamp_utc"] == ""
    assert row["timestamp_source"] == "unavailable_no_rtc"
    assert row["downloaded_at_utc"] == "2026-10-18T12:00:00Z"
    assert row["soil_1_raw"] == "1900"
    assert row["quality_flag"] == "invalid"
    assert "weather_temp" in row
    assert validate(destination) == []


def test_flash_dump_rejects_invalid_sensor_record():
    with pytest.raises(ValueError, match="invalid stored record"):
        parse_flash_payload(["#RLLS_BOOT id=x clock=unsynced", '{"device_ms":1}'])


def test_raw_export_refuses_to_overwrite(tmp_path):
    destination = tmp_path / "log.jsonl"
    write_raw_jsonl(destination, [RECORD])
    with pytest.raises(FileExistsError):
        write_raw_jsonl(destination, [RECORD])
