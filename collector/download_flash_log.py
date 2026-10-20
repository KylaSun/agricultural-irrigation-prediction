from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rlls_demo.flash_log import parse_flash_payload, write_offline_csv, write_raw_jsonl


BEGIN_PREFIX = "#RLLS_LOG_BEGIN"
END_MARKER = "#RLLS_LOG_END"
ERROR_PREFIX = "#RLLS_LOG_ERROR"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the ESP32 LittleFS soil log over USB Serial")
    parser.add_argument("--port", required=True, help="Windows COM port, e.g. COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/live")
    parser.add_argument("--name", help="Output base name; default includes the current UTC time")
    parser.add_argument("--timeout", type=float, default=180.0, help="Seconds to wait for dump completion")
    return parser.parse_args()


def receive_dump(connection, timeout: float) -> list[str]:
    connection.reset_input_buffer()
    connection.write(b"LOG DUMP\n")
    connection.flush()
    deadline = time.monotonic() + timeout
    started = False
    payload: list[str] = []

    while time.monotonic() < deadline:
        raw = connection.readline()
        if not raw:
            continue
        try:
            line = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise RuntimeError("ESP32 returned non-UTF-8 data during log download") from exc
        if line.startswith(ERROR_PREFIX):
            raise RuntimeError(f"ESP32 log error: {line}")
        if not started:
            if line.startswith(BEGIN_PREFIX):
                started = True
            continue
        if line == END_MARKER:
            return payload
        payload.append(line)

    state = "completion marker" if started else "start marker"
    raise TimeoutError(f"timed out waiting for ESP32 log {state}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = arguments()
    try:
        import serial
        from serial import SerialException
    except ImportError:
        logging.error("pyserial is not installed; run pip install -r requirements-collector.txt")
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = args.name or f"esp32_flash_log_{timestamp}"
    jsonl_path = args.output_dir / f"{base_name}.jsonl"
    csv_path = args.output_dir / f"{base_name}.csv"
    if jsonl_path.exists() or csv_path.exists():
        logging.error("output already exists; choose a different --name: %s", base_name)
        return 2

    try:
        with serial.Serial(args.port, args.baud, timeout=1, write_timeout=2) as connection:
            # Opening a common ESP32 USB serial connection may reset the board.
            time.sleep(2.0)
            payload = receive_dump(connection, args.timeout)
        try:
            records = parse_flash_payload(payload)
        except ValueError:
            # Preserve the exact device output for diagnosis. A corrupt or
            # incomplete record must not be silently converted into CSV.
            write_raw_jsonl(jsonl_path, payload)
            logging.error("stored data validation failed; raw log preserved at %s", jsonl_path)
            raise
        if not records:
            logging.warning("ESP32 log is empty; no files were written")
            return 0
        write_raw_jsonl(jsonl_path, payload)
        write_offline_csv(csv_path, records)
    except (SerialException, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logging.error("download failed: %s", exc)
        return 1

    logging.info("downloaded %s records", len(records))
    logging.info("raw log: %s", jsonl_path)
    logging.info("CSV export: %s", csv_path)
    logging.warning("timestamp_utc is blank because this ESP32 has no RTC; use boot_id + device_ms for order")
    logging.info("the ESP32 copy was NOT deleted; clear it only after verifying both files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
