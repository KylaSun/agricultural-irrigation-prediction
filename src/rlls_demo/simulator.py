from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any, Iterator


def simulated_wire_records(seed: int = 42) -> Iterator[dict[str, Any]]:
    rng = random.Random(seed)
    device_ms = 0
    while True:
        phase = device_ms / 60000.0
        record: dict[str, Any] = {
            "schema_version": "2.0.0-demo",
            "device_ms": device_ms,
            "simulated": True,
        }
        for index, offset in enumerate((-3.0, -1.0, 1.5, 3.5), start=1):
            pct = 48.0 + offset + 5.0 * math.sin(phase + index * 0.12)
            record[f"soil_{index}_raw"] = int(3200 - pct * 18)
            record[f"soil_{index}_moisture_pct"] = round(pct + rng.uniform(-0.3, 0.3), 2)
            record[f"soil_{index}_status"] = "simulated"
        yield record
        device_ms += 1000


def enrich_computer_fields(record: dict[str, Any], mode: str = "c2_low_cost_hybrid") -> dict[str, Any]:
    result = dict(record)
    result["timestamp_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result["mode"] = mode
    result["quality_flag"] = "simulated" if result.get("simulated") else "valid"
    result["quality_detail"] = "SIMULATED_DATA" if result.get("simulated") else ""
    return result
