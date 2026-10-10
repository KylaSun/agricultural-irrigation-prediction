import json

import pytest

from rlls_demo.serial_parser import ParseError, parse_serial_line


def wire(**changes):
    value = {
        "schema_version": "2.0.0-demo", "device_ms": 1000,
        "soil_1_raw": 2200, "soil_1_moisture_pct": 55.0, "soil_1_status": "ok",
        "soil_2_raw": 2250, "soil_2_moisture_pct": 52.0, "soil_2_status": "ok",
        "soil_3_raw": 2300, "soil_3_moisture_pct": 49.0, "soil_3_status": "ok",
        "soil_4_raw": 2350, "soil_4_moisture_pct": 46.0, "soil_4_status": "ok",
        "simulated": False,
    }
    value.update(changes)
    return value


def test_parse_valid_line():
    parsed = parse_serial_line(json.dumps(wire()).encode())
    assert parsed.values["soil_1_raw"] == 2200
    assert parsed.values["soil_4_moisture_pct"] == 46.0


def test_wrong_field_count_is_clear():
    value = wire()
    del value["soil_3_raw"]
    with pytest.raises(ParseError, match="missing: soil_3_raw"):
        parse_serial_line(json.dumps(value))


def test_type_conversion_failure_is_rejected():
    with pytest.raises(ParseError, match="soil_2_moisture_pct must be numeric"):
        parse_serial_line(json.dumps(wire(soil_2_moisture_pct="wet")))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"schema_version": "2.0"}, "unsupported schema_version"),
        ({"device_ms": -1}, "device_ms must be in range"),
        ({"soil_1_raw": 2200.5}, "soil_1_raw must be an integer"),
        ({"soil_1_status": "maybe"}, "soil_1_status must be one of"),
        ({"simulated": "false"}, "simulated must be boolean"),
    ],
)
def test_wire_contract_rejects_ambiguous_values(changes, message):
    with pytest.raises(ParseError, match=message):
        parse_serial_line(json.dumps(wire(**changes)))


@pytest.mark.parametrize("line", [b"", b"{broken", b"\xff\xfe", b"# debug only"])
def test_bad_serial_lines_do_not_crash_parser(line):
    with pytest.raises(ParseError):
        parse_serial_line(line)
