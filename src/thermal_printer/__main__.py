from __future__ import annotations

import argparse
import logging
import os
from typing import Sequence

from thermal_printer.agent import AgentConfig, ThermalPrinterAgent, install_signal_handlers
from thermal_printer.driver import ThermalPrinter, ThermalPrinterConfig


def build_printer_config() -> ThermalPrinterConfig:
    return ThermalPrinterConfig(
        port=os.getenv("THERMAL_PRINTER_PORT", "/dev/usb/lp0"),
        baudrate=int(os.getenv("THERMAL_PRINTER_BAUDRATE", "9600")),
        heat_dots=int(os.getenv("THERMAL_PRINTER_HEAT_DOTS", "7")),
        heat_time=int(os.getenv("THERMAL_PRINTER_HEAT_TIME", "80")),
        heat_interval=int(os.getenv("THERMAL_PRINTER_HEAT_INTERVAL", "2")),
        chars_per_line=int(os.getenv("THERMAL_PRINTER_CHARS_PER_LINE", "42")),
        timeout=float(os.getenv("THERMAL_PRINTER_TIMEOUT", "5.0")),
    )


def build_parser(prog: str = "thermal-airprint") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("test-print")
    subparsers.add_parser("agent")
    subparsers.add_parser("status")
    return parser


def main(argv: Sequence[str] | None = None, prog: str = "thermal-airprint") -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    args = build_parser(prog=prog).parse_args(argv)
    printer_config = build_printer_config()

    if args.command == "status":
        available = ThermalPrinter(printer_config).is_available()
        print("available" if available else "unavailable")
        return 0 if available else 1

    if args.command == "test-print":
        with ThermalPrinter(printer_config) as printer:
            printer.print_receipt("Thermal AirPrint\nDFRobot DFR0503\n\nHello from Raspberry Pi!")
        print("test print sent")
        return 0

    base_url = os.getenv("BASE_URL")
    token = os.getenv("AGENT_TOKEN")
    if not base_url or not token:
        raise SystemExit("BASE_URL and AGENT_TOKEN are required for the agent command")

    agent = ThermalPrinterAgent(
        AgentConfig(base_url=base_url, token=token),
        printer_config=printer_config,
    )
    install_signal_handlers(agent)
    agent.run()
    return 0


def agent_main() -> int:
    return main(["agent"], prog="thermal-agent")


if __name__ == "__main__":
    raise SystemExit(main())
