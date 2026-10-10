from rlls_demo.csv_store import CSV_FIELDS, append_csv, read_csv
from rlls_demo.schema import feature_order


def test_csv_round_trip_preserves_missing_as_empty(tmp_path):
    path = tmp_path / "readings.csv"
    append_csv(path, {"timestamp_utc": "2026-10-08T04:00:00Z", "device_ms": 1, "soil_1_raw": None, "soil_1_moisture_pct": 0})
    rows = read_csv(path)
    assert rows[0]["soil_1_raw"] == ""
    assert rows[0]["soil_1_moisture_pct"] == "0"
    assert rows[0]["soil_1_raw"] != rows[0]["soil_1_moisture_pct"]


def test_collection_csv_contains_every_research_model_feature():
    assert "timestamp_utc" in CSV_FIELDS
    assert "soil_composite_pct" in CSV_FIELDS
    assert "soil_composite_count" in CSV_FIELDS
    assert "soil_composite_spread_pct" in CSV_FIELDS
    for mode in ("c1_soil_only", "c2_low_cost_hybrid", "c3_sensor_rich"):
        assert set(feature_order(mode)).issubset(CSV_FIELDS)
