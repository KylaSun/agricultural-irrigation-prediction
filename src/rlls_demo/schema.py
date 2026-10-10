from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import CONFIG_DIR


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_schema(path: str | Path = CONFIG_DIR / "data_schema.json") -> dict[str, Any]:
    return load_json(path)


def load_modes(path: str | Path = CONFIG_DIR / "modes.json") -> dict[str, Any]:
    return load_json(path)


def feature_order(mode: str, modes: dict[str, Any] | None = None) -> list[str]:
    config = modes or load_modes()
    try:
        return list(config["modes"][mode]["feature_order"])
    except KeyError as exc:
        raise ValueError(f"Unknown mode: {mode}") from exc
