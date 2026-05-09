from __future__ import annotations

import base64
import logging
import signal
from dataclasses import dataclass
from time import sleep
from typing import Callable

import httpx

from thermal_printer.driver import ThermalPrinter, ThermalPrinterConfig

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentConfig:
    base_url: str
    token: str
    poll_interval_seconds: float = 5.0
    request_timeout_seconds: float = 30.0
    backoff_max_seconds: float = 60.0


class ThermalPrinterAgent:
    def __init__(
        self,
        config: AgentConfig,
        printer_config: ThermalPrinterConfig | None = None,
        client: httpx.Client | None = None,
        printer_factory: Callable[[], ThermalPrinter] | None = None,
    ) -> None:
        self.config = config
        self._client = client or httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.request_timeout_seconds,
            headers={"X-Agent-Token": config.token},
        )
        self._owns_client = client is None
        self._printer_factory = printer_factory or (lambda: ThermalPrinter(printer_config or ThermalPrinterConfig()))
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def poll_once(self) -> bool:
        response = self._client.get(
            "/api/v1/print-jobs/agent/next",
            params={"token": self.config.token},
        )
        if response.status_code == 204:
            return False
        response.raise_for_status()
        payload = response.json()["data"]
        job_id = str(payload["print_job_id"])
        raw_payload = base64.b64decode(payload["payload_b64"], validate=True)

        ok = True
        error: str | None = None
        try:
            with self._printer_factory() as printer:
                printer.send(raw_payload)
        except Exception as exc:
            ok = False
            error = str(exc)

        result_response = self._client.post(
            f"/api/v1/print-jobs/agent/{job_id}/result",
            params={"token": self.config.token},
            json={"ok": ok, "error": error},
        )
        result_response.raise_for_status()
        if not ok:
            raise RuntimeError(error or "print job failed")
        return True

    def run(self) -> None:
        backoff = self.config.poll_interval_seconds
        try:
            while not self._stop_requested:
                try:
                    had_job = self.poll_once()
                    backoff = self.config.poll_interval_seconds
                    sleep(self.config.poll_interval_seconds if not had_job else 0)
                except KeyboardInterrupt:
                    self.request_stop()
                except Exception:
                    LOGGER.exception("Polling loop failed")
                    if self._stop_requested:
                        break
                    sleep(backoff)
                    backoff = min(backoff * 2, self.config.backoff_max_seconds)
        finally:
            self.close()


def install_signal_handlers(agent: ThermalPrinterAgent) -> None:
    def _handle_signal(_signum: int, _frame: object) -> None:
        agent.request_stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
