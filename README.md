# AirPrintThermalPrinter

Standalone Raspberry Pi project for exposing a DFRobot DFR0503 thermal printer as an AirPrint printer, with an optional HTTPS long-polling agent for remote print jobs.

## Features

- USB printer support through `/dev/usb/lp0`
- GPIO/UART support through `pyserial`
- ESC/POS driver with receipt helpers
- CUPS + Avahi setup script for AirPrint discovery
- CUPS filter for converting text/PDF/PostScript jobs to ESC/POS
- Optional long-polling agent for remote queued jobs

## Project Layout

```text
thermal-airprint/
├── README.md
├── pyproject.toml
├── scripts/
│   ├── setup_airprint.sh
│   ├── cups_thermal_filter.sh
│   └── thermal_printer.ppd
├── src/
│   └── thermal_printer/
│       ├── __init__.py
│       ├── driver.py
│       ├── agent.py
│       └── __main__.py
├── tests/
│   ├── test_agent.py
│   └── test_driver.py
└── systemd/
    └── thermal-agent.service
```

## Install

```bash
python -m pip install -e '.[dev]'
```

## AirPrint setup

Run the setup script as root on the Raspberry Pi:

```bash
sudo ./scripts/setup_airprint.sh
```

After setup, verify:

```bash
echo "Hello AirPrint!" | lp -d Thermal-AirPrint
```

## CLI

```bash
thermal-airprint test-print
thermal-airprint status
BASE_URL=https://example.com AGENT_TOKEN=secret thermal-airprint agent
```

The thermal printer requires its own 9V barrel jack power supply even when USB is connected for data.
