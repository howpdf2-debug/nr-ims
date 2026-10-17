"""Test that sensitive keys are redacted from structured logs."""

import json

import pytest
import structlog

from app.logging_config import configure_logging


def test_sensitive_keys_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger().info(
        "evt", password="hunter2", snmp_community="public", ok="yes"
    )
    out = capsys.readouterr().out
    record = json.loads(out.strip().splitlines()[-1])
    assert record["password"] == "***REDACTED***"
    assert record["snmp_community"] == "***REDACTED***"
    assert record["ok"] == "yes"