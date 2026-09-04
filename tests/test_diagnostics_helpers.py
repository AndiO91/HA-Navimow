"""Tests for diagnostic serialization and redaction."""

import importlib.util
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "navimow_plus"
    / "diagnostics_helpers.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "navimow_diagnostics_helpers", _MODULE_PATH
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
diagnostics_value = _MODULE.diagnostics_value
redact_diagnostics = _MODULE.redact_diagnostics


class _State(Enum):
    MOWING = "mowing"


@dataclass
class _Message:
    device_id: str
    state: _State
    timestamp: datetime


class DiagnosticsHelpersTest(unittest.TestCase):
    def test_serializes_sdk_style_values(self) -> None:
        value = diagnostics_value(
            _Message(
                "secret-id",
                _State.MOWING,
                datetime(2026, 9, 4, tzinfo=timezone.utc),
            )
        )
        self.assertEqual(value["state"], "mowing")
        self.assertEqual(value["timestamp"], "2026-09-04T00:00:00+00:00")

    def test_recursively_redacts_secrets_ids_and_position(self) -> None:
        value = redact_diagnostics(
            {
                "token": {"access_token": "secret"},
                "refreshToken": "secret-refresh-token",
                "devices": [
                    {
                        "device_id": "abc",
                        "serial_number": "123",
                        "position": {"lat": 51.0, "lng": 7.0},
                        "model": "i105E",
                    }
                ],
            }
        )
        self.assertEqual(value["token"], "**REDACTED**")
        self.assertEqual(value["refreshToken"], "**REDACTED**")
        self.assertEqual(value["devices"][0]["device_id"], "**REDACTED**")
        self.assertEqual(value["devices"][0]["serial_number"], "**REDACTED**")
        self.assertEqual(value["devices"][0]["position"], "**REDACTED**")
        self.assertEqual(value["devices"][0]["model"], "i105E")


if __name__ == "__main__":
    unittest.main()
