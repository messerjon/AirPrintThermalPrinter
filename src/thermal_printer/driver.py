from __future__ import annotations

import os
from dataclasses import dataclass
from time import sleep
from types import TracebackType
from typing import Any, BinaryIO, Literal

CMD_INIT = b"\x1b@"
CMD_FEED = b"\x1bd"
CMD_ALIGN = b"\x1ba"
CMD_BOLD = b"\x1bE"
CMD_UNDERLINE = b"\x1b-"
CMD_SIZE = b"\x1d!"
CMD_CUT = b"\x1dV\x00"
CMD_HEAT = b"\x1b7"
CMD_CHARSET = b"\x1bR"


@dataclass(frozen=True)
class ThermalPrinterConfig:
    port: str = "/dev/usb/lp0"
    baudrate: int = 9600
    heat_dots: int = 7
    heat_time: int = 80
    heat_interval: int = 2
    chars_per_line: int = 42
    timeout: float = 5.0

    def __post_init__(self) -> None:
        if self.heat_dots > 7:
            raise ValueError("heat_dots must be <= 7")


class ThermalPrinter:
    def __init__(self, config: ThermalPrinterConfig | None = None) -> None:
        self.config = config or ThermalPrinterConfig()
        self._handle: BinaryIO | Any | None = None

    def __enter__(self) -> "ThermalPrinter":
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def open(self) -> None:
        if self._handle is not None:
            return
        if self.config.port.startswith("/dev/usb/"):
            self._handle = open(self.config.port, "wb", buffering=0)
        else:
            import serial

            self._handle = serial.Serial(
                self.config.port,
                self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )
        sleep(0.5)
        self.send(CMD_INIT)
        sleep(0.1)
        self.send(CMD_HEAT + bytes([self.config.heat_dots, self.config.heat_time, self.config.heat_interval]))
        self.send(CMD_CHARSET + b"\x00")
        self._flush()
        sleep(0.1)

    def close(self) -> None:
        if self._handle is None:
            return
        try:
            self._flush()
        finally:
            self._handle.close()
            self._handle = None

    def send(self, payload: bytes) -> None:
        if self._handle is None:
            raise RuntimeError("printer is not open")
        self._handle.write(payload)
        self._flush()

    def is_available(self) -> bool:
        return os.path.exists(self.config.port)

    def print_text(self, text: str) -> None:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized and not normalized.endswith("\n"):
            normalized += "\n"
        self.send(normalized.encode("cp437", errors="replace"))
        self.feed(3)

    def print_receipt(self, text: str) -> None:
        self.send(CMD_INIT)
        self.reset_formatting()
        self.print_text(text)
        self.cut()

    def set_align(self, align: Literal["left", "center", "right"]) -> None:
        mapping = {"left": 0, "center": 1, "right": 2}
        self.send(CMD_ALIGN + bytes([mapping[align]]))

    def set_bold(self, on: bool) -> None:
        self.send(CMD_BOLD + bytes([1 if on else 0]))

    def set_size(self, width: int, height: int) -> None:
        if width < 1 or width > 8 or height < 1 or height > 8:
            raise ValueError("width and height must be between 1 and 8")
        value = ((width - 1) << 4) | (height - 1)
        self.send(CMD_SIZE + bytes([value]))

    def feed(self, lines: int) -> None:
        if lines < 0 or lines > 255:
            raise ValueError("lines must be between 0 and 255")
        self.send(CMD_FEED + bytes([lines]))

    def cut(self) -> None:
        self.send(CMD_CUT)

    def print_separator(self, char: str = "-") -> None:
        fill = (char or "-")[0]
        self.send((fill * self.config.chars_per_line + "\n").encode("cp437", errors="replace"))

    def reset_formatting(self) -> None:
        self.set_align("left")
        self.set_bold(False)
        self.send(CMD_UNDERLINE + b"\x00")
        self.set_size(1, 1)

    def _flush(self) -> None:
        if self._handle is not None and hasattr(self._handle, "flush"):
            self._handle.flush()
