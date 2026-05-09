import builtins

import pytest

from thermal_printer import driver
from thermal_printer.driver import ThermalPrinter, ThermalPrinterConfig


class FakeHandle:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.writes.append(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_open_usb_printer_sends_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    handle = FakeHandle()
    monkeypatch.setattr(driver, "sleep", lambda *_args: None)
    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: handle)

    printer = ThermalPrinter(ThermalPrinterConfig(port="/dev/usb/lp0"))
    printer.open()

    assert b"".join(handle.writes) == (
        driver.CMD_INIT
        + driver.CMD_HEAT
        + bytes([7, 80, 2])
        + driver.CMD_CHARSET
        + b"\x00"
    )


def test_print_receipt_outputs_text_feed_and_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    handle = FakeHandle()
    monkeypatch.setattr(driver, "sleep", lambda *_args: None)
    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: handle)

    printer = ThermalPrinter(ThermalPrinterConfig(port="/dev/usb/lp0"))
    printer.open()
    handle.writes.clear()

    printer.print_receipt("Hello")

    assert handle.writes[0] == driver.CMD_INIT
    assert b"Hello\n" in handle.writes
    assert driver.CMD_FEED + b"\x03" in handle.writes
    assert handle.writes[-1] == driver.CMD_CUT


def test_send_writes_raw_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    handle = FakeHandle()
    monkeypatch.setattr(driver, "sleep", lambda *_args: None)
    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: handle)

    printer = ThermalPrinter(ThermalPrinterConfig(port="/dev/usb/lp0"))
    printer.open()
    handle.writes.clear()

    printer.send(b"\x1b@\x1dV\x00")

    assert handle.writes == [b"\x1b@\x1dV\x00"]


@pytest.mark.parametrize("width,height", [(0, 1), (9, 1), (1, 0), (1, 9)])
def test_set_size_validates_range(width: int, height: int) -> None:
    printer = ThermalPrinter()
    with pytest.raises(ValueError):
        printer.set_size(width, height)


def test_is_available_uses_device_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(driver.os.path, "exists", lambda path: path == "/dev/usb/lp0")
    assert ThermalPrinter(ThermalPrinterConfig(port="/dev/usb/lp0")).is_available() is True
    assert ThermalPrinter(ThermalPrinterConfig(port="/dev/serial0")).is_available() is False


def test_heat_dots_validates_supported_range() -> None:
    with pytest.raises(ValueError):
        ThermalPrinterConfig(heat_dots=-1)


@pytest.mark.parametrize("lines", [-1, 256])
def test_feed_validates_range(lines: int) -> None:
    printer = ThermalPrinter()
    with pytest.raises(ValueError):
        printer.feed(lines)
