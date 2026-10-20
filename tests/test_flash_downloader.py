from collections import deque
from types import ModuleType, SimpleNamespace
import sys

import pytest

from collector import download_flash_log
from collector.download_flash_log import receive_dump


class FakeSerial:
    def __init__(self, lines):
        self.lines = deque(line.encode("utf-8") + b"\n" for line in lines)
        self.written = b""

    def reset_input_buffer(self):
        pass

    def write(self, value):
        self.written += value

    def flush(self):
        pass

    def readline(self):
        return self.lines.popleft() if self.lines else b""


def test_receive_dump_ignores_live_stream_outside_markers():
    connection = FakeSerial([
        '{"live":"record"}',
        "#RLLS_LOG_BEGIN bytes=20",
        "#RLLS_BOOT id=a1 clock=unsynced",
        '{"stored":"record"}',
        "#RLLS_LOG_END",
        '{"live":"later"}',
    ])
    assert receive_dump(connection, timeout=0.1) == [
        "#RLLS_BOOT id=a1 clock=unsynced",
        '{"stored":"record"}',
    ]
    assert connection.written == b"LOG DUMP\n"


def test_receive_dump_surfaces_firmware_error():
    connection = FakeSerial(["#RLLS_LOG_ERROR storage_not_mounted"])
    with pytest.raises(RuntimeError, match="storage_not_mounted"):
        receive_dump(connection, timeout=0.1)


def test_invalid_stored_record_preserves_raw_dump_without_csv(tmp_path, monkeypatch):
    connection = FakeSerial([
        "#RLLS_LOG_BEGIN bytes=20",
        "#RLLS_BOOT id=a1 clock=unsynced",
        '{"device_ms":1}',
        "#RLLS_LOG_END",
    ])
    connection.__enter__ = lambda self: self
    connection.__exit__ = lambda self, *args: None

    class FakePort:
        def __enter__(self):
            return connection

        def __exit__(self, *args):
            return None

    fake_serial = ModuleType("serial")
    fake_serial.SerialException = type("SerialException", (Exception,), {})
    fake_serial.Serial = lambda *args, **kwargs: FakePort()
    monkeypatch.setitem(sys.modules, "serial", fake_serial)
    monkeypatch.setattr(download_flash_log.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        download_flash_log,
        "arguments",
        lambda: SimpleNamespace(
            port="COM3",
            baud=115200,
            output_dir=tmp_path,
            name="corrupt",
            timeout=0.1,
        ),
    )

    assert download_flash_log.main() == 1
    assert (tmp_path / "corrupt.jsonl").read_text(encoding="utf-8").endswith('{"device_ms":1}\n')
    assert not (tmp_path / "corrupt.csv").exists()
