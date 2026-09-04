"""Tests for pure Navimow Plus helpers."""

import importlib.util
import unittest
from dataclasses import dataclass
from pathlib import Path

_HELPERS_PATH = (
    Path(__file__).parents[1] / "custom_components" / "navimow_plus" / "helpers.py"
)
_SPEC = importlib.util.spec_from_file_location("navimow_plus_helpers", _HELPERS_PATH)
assert _SPEC and _SPEC.loader
_HELPERS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_HELPERS)
error_value = _HELPERS.error_value
extract_position = _HELPERS.extract_position
status_refresh_due = _HELPERS.status_refresh_due


@dataclass
class _Message:
    error: dict | None = None
    state: str | None = None
    level: str | None = None
    message: str | None = None
    event: str | None = None


class HelpersTest(unittest.TestCase):
    def test_status_refresh_due_uses_real_freshness(self) -> None:
        self.assertFalse(
            status_refresh_due(
                now=100,
                last_mqtt_state=90,
                last_http_fetch=None,
                mqtt_stale_seconds=30,
                http_min_interval=60,
            )
        )
        self.assertFalse(
            status_refresh_due(
                now=100,
                last_mqtt_state=10,
                last_http_fetch=80,
                mqtt_stale_seconds=30,
                http_min_interval=60,
            )
        )
        self.assertTrue(
            status_refresh_due(
                now=100,
                last_mqtt_state=10,
                last_http_fetch=20,
                mqtt_stale_seconds=30,
                http_min_interval=60,
            )
        )

    def test_forced_status_refresh_bypasses_cache_windows(self) -> None:
        self.assertTrue(
            status_refresh_due(
                now=100,
                last_mqtt_state=100,
                last_http_fetch=100,
                mqtt_stale_seconds=300,
                http_min_interval=300,
                force=True,
            )
        )

    def test_extract_position_accepts_known_keys(self) -> None:
        self.assertEqual(extract_position({"lat": "51.2", "lng": 7.1}), (51.2, 7.1))
        self.assertEqual(
            extract_position({"latitude": 51.2, "longitude": 7.1}),
            (51.2, 7.1),
        )

    def test_extract_position_rejects_invalid_coordinates(self) -> None:
        self.assertIsNone(extract_position(None))
        self.assertIsNone(extract_position({"lat": 91, "lng": 7.1}))
        self.assertIsNone(extract_position({"lat": 0, "lng": 0}))
        self.assertIsNone(extract_position({"lat": "invalid", "lng": 7.1}))

    def test_error_value_prefers_state_error(self) -> None:
        state = _Message(error={"code": "lifted", "message": "Mower lifted"})
        event = _Message(level="error", message="Older event")
        self.assertEqual(error_value(state, event), "Mower lifted")

    def test_error_value_uses_error_event(self) -> None:
        self.assertEqual(
            error_value(_Message(), _Message(level="error", event="blocked")),
            "blocked",
        )
        self.assertIsNone(
            error_value(_Message(), _Message(level="info", event="ready"))
        )

    def test_error_value_reports_error_state_without_details(self) -> None:
        state = _Message(state="error")
        self.assertEqual(error_value(state, None), "error")


if __name__ == "__main__":
    unittest.main()
