"""Project-wide pytest setup.

Use a new workspace-local temp directory for each test process.  Reusing one
fixed directory can fail on Windows when antivirus/indexing briefly retains a
handle, while the default user Temp directory is not writable in every Codex
runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


def pytest_configure(config) -> None:
    if config.option.basetemp is None:
        temp_root = Path(".pytest-runs")
        temp_root.mkdir(parents=True, exist_ok=True)
        run_id = f"run-{os.getpid()}-{uuid4().hex[:8]}"
        config.option.basetemp = str(temp_root / run_id)
