from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def _post_chat(log_path: Path, request_id: str | None = None) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = {"x-request-id": request_id} if request_id else {}
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                headers=headers,
                json={
                    "user_id": "student@example.com",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "student@example.com 090 123 4567 4111 1111 1111 1111",
                },
            )

    return asyncio.run(send_request())


def test_chat_propagates_supplied_request_id_and_scrubs_log(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    response = _post_chat(log_path, "req-deadbeef")

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-deadbeef"
    assert float(response.headers["x-response-time-ms"]) >= 0

    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    request_log = next(record for record in records if record["event"] == "request_received")
    assert request_log["correlation_id"] == "req-deadbeef"
    assert request_log["user_id_hash"] != "student@example.com"
    assert request_log["session_id"] == "session-01"
    assert request_log["feature"] == "qa"
    assert request_log["model"]
    assert request_log["env"]

    raw_log = log_path.read_text()
    assert "student@example.com" not in raw_log
    assert "090 123 4567" not in raw_log
    assert "4111 1111 1111 1111" not in raw_log
    assert "[REDACTED_EMAIL]" in raw_log
    assert "[REDACTED_PHONE_VN]" in raw_log
    assert "[REDACTED_CREDIT_CARD]" in raw_log


def test_chat_generates_valid_request_id_for_invalid_input(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    response = _post_chat(log_path, "invalid-request-id")

    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.json()["correlation_id"] == correlation_id
