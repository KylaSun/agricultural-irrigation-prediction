from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rlls_demo.csv_store import append_csv
from rlls_demo.preprocessing import process_record
from rlls_demo.serial_parser import ParseError, parse_serial_line
from rlls_demo.simulator import enrich_computer_fields, simulated_wire_records


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect ESP32 JSON Lines into CSV")
    parser.add_argument("--port", help="Windows COM port, e.g. COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/live/sensor_readings.csv")
    parser.add_argument("--mode", choices=["c1_soil_only", "c2_low_cost_hybrid", "c3_sensor_rich", "weather_only"], default="c2_low_cost_hybrid")
    parser.add_argument(
        "--active-probe",
        choices=["soil_1", "soil_2", "soil_3", "soil_4", "soil_composite"],
        default="soil_1",
        help="Soil input source; soil_composite is the median of at least two valid probes",
    )
    parser.add_argument("--simulate", action="store_true", help="Generate clearly labelled simulated records")
    parser.add_argument("--interval", type=float, default=1.0, help="Simulation interval in seconds")
    parser.add_argument("--max-records", type=int, default=0, help="0 means keep running")
    parser.add_argument("--retries", type=int, default=5)
    return parser.parse_args()


def accept_wire_record(wire: dict, output: Path, mode: str, active_probe: str = "soil_1") -> None:
    record = enrich_computer_fields(wire, mode)
    checked = process_record(record, mode, active_probe=active_probe, stale_after_seconds=10)
    append_csv(output, checked.record)


def run_simulation(args: argparse.Namespace) -> int:
    logging.warning("SIMULATED DATA MODE: no ESP32 is being read")
    for index, wire in enumerate(simulated_wire_records(), start=1):
        accept_wire_record(wire, args.output, args.mode, args.active_probe)
        logging.info("saved simulated record %s to %s", index, args.output)
        if args.max_records and index >= args.max_records:
            return 0
        time.sleep(max(0.0, args.interval))
    return 0


def run_serial(args: argparse.Namespace) -> int:
    if not args.port:
        logging.error("--port is required unless --simulate is used")
        return 2
    try:
        import serial
        from serial import SerialException
    except ImportError:
        logging.error("pyserial is not installed; run pip install -r requirements-demo.txt")
        return 2

    attempts = 0
    saved = 0
    while attempts < args.retries:
        try:
            with serial.Serial(args.port, args.baud, timeout=2) as connection:
                logging.info("connected to %s at %s baud", args.port, args.baud)
                attempts = 0
                while True:
                    raw = connection.readline()
                    if not raw:
                        logging.warning("serial timeout: no complete line received")
                        continue
                    try:
                        wire = parse_serial_line(raw).values
                        accept_wire_record(wire, args.output, args.mode, args.active_probe)
                        saved += 1
                        if args.max_records and saved >= args.max_records:
                            return 0
                    except ParseError as exc:
                        logging.warning("discarded serial record: %s", exc)
                    except (TypeError, ValueError) as exc:
                        logging.warning("record failed validation: %s", exc)
        except (SerialException, OSError) as exc:
            attempts += 1
            if attempts >= args.retries:
                logging.error("serial unavailable after %s attempts: %s", attempts, exc)
                return 1
            wait = min(2 ** attempts, 10)
            logging.warning("serial unavailable (%s/%s): %s; retrying in %ss", attempts, args.retries, exc, wait)
            time.sleep(wait)
    return 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = arguments()
    return run_simulation(args) if args.simulate else run_serial(args)


if __name__ == "__main__":
    raise SystemExit(main())
