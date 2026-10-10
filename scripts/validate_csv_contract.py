from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rlls_demo.csv_store import CSV_FIELDS
from rlls_demo.schema import feature_order


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a collector/replay CSV against the RLLS demo and C1/C2/C3 input contracts."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=PROJECT_ROOT / "data" / "replay" / "simulated_normal.csv",
    )
    return parser.parse_args()


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"file not found: {path}"]

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = list(reader)

    missing_headers = [field for field in CSV_FIELDS if field not in headers]
    if missing_headers:
        errors.append(f"missing collector columns: {', '.join(missing_headers)}")
    if not rows:
        errors.append("CSV has no data rows")

    for mode in ("c1_soil_only", "c2_low_cost_hybrid", "c3_sensor_rich"):
        missing_features = [field for field in feature_order(mode) if field not in headers]
        if missing_features:
            errors.append(f"{mode} missing model features: {', '.join(missing_features)}")

    for row_number, row in enumerate(rows, start=2):
        timestamp = row.get("timestamp_utc", "")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timezone missing")
        except ValueError as exc:
            errors.append(f"row {row_number} invalid timestamp_utc: {exc}")
            break
    return errors


def main() -> int:
    path = arguments().path.resolve()
    errors = validate(path)
    if errors:
        print(f"FAIL: {path}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"PASS: {path}")
    print("- collector/replay columns are complete")
    print("- C1/C2/C3 feature names are present")
    print("- timestamp_utc values include timezone information")
    print("NOTE: this is not the historical training-table format; see docs/CSV_COMPATIBILITY_CN.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
