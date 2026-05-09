import base64
import json

import httpx
import pytest

from thermal_printer.agent import AgentConfig, ThermalPrinterAgent


class FakePrinter:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []

    def __enter__(self) -> "FakePrinter":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def send(self, payload: bytes) -> None:
        self.payloads.append(payload)


def test_poll_once_prints_payload_and_reports_success() -> None:
    printer = FakePrinter()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "print_job_id": "job-1",
                        "payload_b64": base64.b64encode(b"hello").decode("ascii"),
                    }
                },
            )
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://example.com",
        headers={"X-Agent-Token": "token"},
    )
    agent = ThermalPrinterAgent(
        AgentConfig(base_url="https://example.com", token="token"),
        client=client,
        printer_factory=lambda: printer,
    )

    assert agent.poll_once() is True
    assert printer.payloads == [b"hello"]
    assert requests[0].headers["X-Agent-Token"] == "token"
    assert json.loads(requests[1].content) == {"ok": True, "error": None}


def test_poll_once_reports_failure_when_printing_raises() -> None:
    class BrokenPrinter(FakePrinter):
        def send(self, payload: bytes) -> None:
            raise OSError("device offline")

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "print_job_id": "job-2",
                        "payload_b64": base64.b64encode(b"hello").decode("ascii"),
                    }
                },
            )
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://example.com",
        headers={"X-Agent-Token": "token"},
    )
    agent = ThermalPrinterAgent(
        AgentConfig(base_url="https://example.com", token="token"),
        client=client,
        printer_factory=BrokenPrinter,
    )

    with pytest.raises(RuntimeError, match="device offline"):
        agent.poll_once()

    assert json.loads(requests[1].content) == {"ok": False, "error": "device offline"}
