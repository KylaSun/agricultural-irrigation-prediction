from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .csv_store import CSV_FIELDS
from .serial_parser import ParseError, parse_serial_line


BOOT_PREFIX = "#RLLS_BOOT "
OFFLINE_CSV_FIELDS = tuple(CSV_FIELDS)


@dataclass(frozen=True)
class OfflineRecord:
    boot_id: str | None
    values: dict


def _boot_id(line: str) -> str | None:
    if not line.startswith(BOOT_PREFIX):
        return None
    for token in line[len(BOOT_PREFIX):].split():
        if token.startswith("id="):
            value = token.removeprefix("id=").strip()
            return value or None
    return None


def parse_flash_payload(lines: Iterable[str]) -> list[OfflineRecord]:
    """Parse a firmware dump while retaining the boot segment of each sample."""

    records: list[OfflineRecord] = []
    current_boot_id: str | None = None
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(BOOT_PREFIX):
            current_boot_id = _boot_id(line)
            continue
        if line.startswith("#"):
            continue
        try:
            values = parse_serial_line(line).values
        except ParseError as exc:
            raise ValueError(f"invalid stored record at payload line {line_number}: {exc}") from exc
        records.append(OfflineRecord(current_boot_id, values))
    return records


def write_raw_jsonl(path: str | Path, lines: Iterable[str]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line.rstrip("\r\n") + "\n")


def write_offline_csv(
    path: str | Path,
    records: Iterable[OfflineRecord],
    *,
    downloaded_at: datetime | None = None,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    observed = (downloaded_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    downloaded_at_utc = observed.isoformat(timespec="seconds").replace("+00:00", "Z")
    with destination.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OFFLINE_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {
                "boot_id": record.boot_id or "",
                # No RTC is installed. Empty means unknown, never zero and never
                # silently replaced with the retrieval time.
                "timestamp_utc": "",
                "timestamp_source": "unavailable_no_rtc",
                "downloaded_at_utc": downloaded_at_utc,
                "quality_flag": "invalid",
                "quality_detail": "timestamp_utc unavailable: ESP32 has no RTC",
                **record.values,
            }
            writer.writerow(row)


def json_record_count(path: str | Path) -> int:
    count = 0
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                json.loads(line)
                count += 1
    return count
