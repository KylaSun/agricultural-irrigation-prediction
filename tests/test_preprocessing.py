from datetime import datetime, timezone

from rlls_demo.preprocessing import process_record
from rlls_demo.schema import feature_order, load_modes


NOW = datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc)


def record(**changes):
    base = {
        "timestamp_utc": "2026-10-08T04:00:00Z", "device_ms": 1000,
        "soil_1_raw": 2200, "soil_1_moisture_pct": 55, "soil_1_status": "ok",
        "soil_2_raw": 2250, "soil_2_moisture_pct": 52, "soil_2_status": "ok",
        "soil_3_raw": 2300, "soil_3_moisture_pct": 49, "soil_3_status": "ok",
        "soil_4_raw": 2350, "soil_4_moisture_pct": 46, "soil_4_status": "ok",
        "weather_temp": 23, "weather_humidity": 62, "weather_rain": 0,
        "weather_pressure": 1012, "weather_wind_speed": 8, "weather_radiation": 400,
        "simulated": False, "mode": "c2_low_cost_hybrid", "quality_flag": "valid", "quality_detail": "",
    }
    base.update(changes)
    return base


def test_missing_is_not_zero():
    result = process_record(record(soil_1_moisture_pct=""), "c1_soil_only", now=NOW)
    assert result.features["soil_moisture"] is None
    assert result.features["soil_moisture"] != 0
    assert result.quality_flag == "missing"


def test_out_of_range_is_null_with_reason():
    result = process_record(record(soil_2_moisture_pct=120), "c1_soil_only", active_probe="soil_2", now=NOW)
    assert result.features["soil_moisture"] is None
    assert result.quality_flag == "out_of_range"
    assert any("soil_2_moisture_pct: out_of_range" in issue for issue in result.issues)


def test_stale_detection():
    result = process_record(record(timestamp_utc="2026-10-08T03:59:00Z"), "weather_only", now=NOW, stale_after_seconds=10)
    assert result.quality_flag == "stale"


def test_feature_order_is_fixed():
    modes = load_modes()
    for mode, definition in modes["modes"].items():
        assert feature_order(mode, modes) == definition["feature_order"]


def test_research_configurations_match_c1_c2_c3():
    c1 = feature_order("c1_soil_only")
    c2 = feature_order("c2_low_cost_hybrid")
    c3 = feature_order("c3_sensor_rich")
    weather = feature_order("weather_only")
    assert c1 == ["soil_moisture"]
    assert c2 == c1 + weather
    assert c3 == c2 + ["soil_temperature_0-7cm", "soil_temperature_7-18cm", "ec", "ph", "water_vol_past_4h"]
    assert weather == ["weather_temp", "weather_humidity", "weather_rain", "weather_pressure", "weather_wind_speed", "weather_radiation"]


def test_disabled_sensor_reaches_model_as_missing():
    result = process_record(record(), "c1_soil_only", now=NOW, disabled_fields={"soil_1_moisture_pct"})
    assert result.features["soil_moisture"] is None
    assert any("disabled" in issue for issue in result.issues)


def test_active_probe_maps_one_position_not_four_feature_average():
    result = process_record(record(), "c1_soil_only", active_probe="soil_3", now=NOW)
    assert result.features == {"soil_moisture": 49.0}


def test_composite_uses_median_and_reports_support():
    result = process_record(record(), "c1_soil_only", active_probe="soil_composite", now=NOW)
    assert result.features == {"soil_moisture": 50.5}
    assert result.record["soil_composite_pct"] == 50.5
    assert result.record["soil_composite_count"] == 4
    assert result.record["soil_composite_spread_pct"] == 9.0


def test_composite_excludes_missing_instead_of_using_zero():
    result = process_record(
        record(soil_1_moisture_pct=None),
        "c1_soil_only",
        active_probe="soil_composite",
        now=NOW,
    )
    assert result.features == {"soil_moisture": 49.0}
    assert result.record["soil_composite_count"] == 3


def test_composite_requires_two_valid_probes():
    disabled = {"soil_1_moisture_pct", "soil_2_moisture_pct", "soil_3_moisture_pct"}
    result = process_record(
        record(),
        "c1_soil_only",
        active_probe="soil_composite",
        now=NOW,
        disabled_fields=disabled,
    )
    assert result.features["soil_moisture"] is None
    assert result.record["soil_composite_count"] == 1
    assert any("fewer than 2 valid probes" in issue for issue in result.issues)
