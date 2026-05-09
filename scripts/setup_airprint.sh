#!/usr/bin/env bash
set -euo pipefail

PRINTER_NAME="Thermal-AirPrint"
PRINTER_DESC="Thermal Printer (DFR0503)"
PRINTER_LOCATION="Kitchen"
DEVICE_URI="usb://Gprinter/GP-58"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run with sudo." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILTER_SRC="${SCRIPT_DIR}/cups_thermal_filter.sh"
FILTER_DEST="/usr/lib/cups/filter/thermal_escpos"
PPD_SRC="${SCRIPT_DIR}/thermal_printer.ppd"
PPD_DEST="/etc/cups/ppd/${PRINTER_NAME}.ppd"
AVAHI_DEST="/etc/avahi/services/airprint-thermal.service"

export PRINTER_NAME PRINTER_DESC PRINTER_LOCATION

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  cups \
  cups-filters \
  avahi-daemon \
  python3-cups \
  libnss-mdns \
  ghostscript

python3 - <<'PY'
from pathlib import Path
import os
import re

path = Path("/etc/cups/cupsd.conf")
text = path.read_text()

text = re.sub(r"(?m)^Listen\s+localhost:631\s*$", "Port 631", text)
if "Port 631" not in text:
    text = f"Port 631\n{text}"

for directive in ("WebInterface Yes", "Browsing On", "DefaultShared Yes"):
    if re.search(rf"(?m)^{re.escape(directive)}\s*$", text) is None:
        text += f"\n{directive}\n"

for block in ("/", "/admin", "/admin/conf"):
    pattern = re.compile(rf"(<Location {re.escape(block)}>\n)(.*?)(\n</Location>)", re.S)
    match = pattern.search(text)
    if not match:
        continue
    body = match.group(2)
    if "Allow @LOCAL" not in body:
        body = f"{body}\n  Allow @LOCAL"
    text = text[:match.start()] + match.group(1) + body + match.group(3) + text[match.end():]

path.write_text(text)
PY

cupsctl --remote-admin --remote-any --share-printers

if [[ -n "${SUDO_USER:-}" ]]; then
  usermod -a -G lpadmin "${SUDO_USER}"
fi

install -m 0755 "${FILTER_SRC}" "${FILTER_DEST}"
install -m 0644 "${PPD_SRC}" "${PPD_DEST}"

lpadmin \
  -p "${PRINTER_NAME}" \
  -E \
  -v "${DEVICE_URI}" \
  -P "${PPD_DEST}" \
  -D "${PRINTER_DESC}" \
  -L "${PRINTER_LOCATION}" \
  -o printer-is-shared=true

cupsenable "${PRINTER_NAME}"
cupsaccept "${PRINTER_NAME}"

cat > "${AVAHI_DEST}" <<EOF
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">${PRINTER_NAME}</name>
  <service>
    <type>_ipp._tcp</type>
    <subtype>_universal._sub._ipp._tcp</subtype>
    <port>631</port>
    <txt-record>txtvers=1</txt-record>
    <txt-record>qtotal=1</txt-record>
    <txt-record>rp=printers/${PRINTER_NAME}</txt-record>
    <txt-record>ty=${PRINTER_DESC}</txt-record>
    <txt-record>product=(GPL Ghostscript)</txt-record>
    <txt-record>pdl=application/octet-stream,application/pdf,application/postscript,image/jpeg,image/png,image/urf</txt-record>
    <txt-record>URF=W8,SRGB24,CP1,RS600</txt-record>
    <txt-record>note=${PRINTER_LOCATION}</txt-record>
  </service>
</service-group>
EOF

systemctl enable cups avahi-daemon
systemctl restart cups avahi-daemon
