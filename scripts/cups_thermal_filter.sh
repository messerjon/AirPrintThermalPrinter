#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${6:-}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

SOURCE_FILE="${WORK_DIR}/job-input"
TEXT_FILE="${WORK_DIR}/job-text.txt"

if [[ -n "${INPUT_FILE}" ]]; then
  cat "${INPUT_FILE}" > "${SOURCE_FILE}"
else
  cat > "${SOURCE_FILE}"
fi

MIME_TYPE="${CONTENT_TYPE:-$(file --brief --mime-type "${SOURCE_FILE}")}"

case "${MIME_TYPE}" in
  text/*|application/octet-stream)
    cp "${SOURCE_FILE}" "${TEXT_FILE}"
    ;;
  application/pdf|application/postscript|image/png|image/jpeg|image/urf)
    gs -q -dSAFER -dBATCH -dNOPAUSE \
      -sDEVICE=txtwrite \
      -sOutputFile="${TEXT_FILE}" \
      "${SOURCE_FILE}"
    ;;
  *)
    echo "Unsupported MIME type: ${MIME_TYPE}" >&2
    exit 1
    ;;
esac

python3 - "${TEXT_FILE}" <<'PY'
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

text = Path(sys.argv[1]).read_text(errors="replace")
payload = bytearray(b"\x1b@\x1b7\x07\x50\x02\x1bR\x00")

for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
    wrapped = textwrap.wrap(raw_line, width=42) or [""]
    for line in wrapped:
        payload.extend(line.encode("cp437", errors="replace"))
        payload.extend(b"\n")

payload.extend(b"\x1bd\x03\x1dV\x00")
sys.stdout.buffer.write(payload)
PY
