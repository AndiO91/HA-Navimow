"""Serialization and redaction helpers for Navimow diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

REDACTED = "**REDACTED**"

_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "account_id",
        "address",
        "auth_headers",
        "authorization",
        "client_id",
        "client_secret",
        "device_id",
        "entry_id",
        "email",
        "id",
        "ip",
        "ip_address",
        "latitude",
        "longitude",
        "location",
        "lat",
        "lng",
        "mac",
        "mqtt_password",
        "mqtt_username",
        "name",
        "password",
        "phone",
        "position",
        "pwd_info",
        "pwdinfo",
        "refresh_token",
        "serial_number",
        "sn",
        "ssid",
        "token",
        "uid",
        "unique_id",
        "user_name",
        "username",
        "uuid",
        "ws_path",
    }
)

_SENSITIVE_COMPACT_KEYS = frozenset(key.replace("_", "") for key in _SENSITIVE_KEYS)


def diagnostics_value(value: Any, *, depth: int = 0) -> Any:
    """Convert SDK values into JSON-compatible diagnostic data."""
    if depth > 10:
        return "<maximum depth reached>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return diagnostics_value(value.value, depth=depth + 1)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): diagnostics_value(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [diagnostics_value(item, depth=depth + 1) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return diagnostics_value(asdict(value), depth=depth + 1)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return diagnostics_value(model_dump(mode="json"), depth=depth + 1)
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return diagnostics_value(dict_method(), depth=depth + 1)
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return diagnostics_value(
            {key: item for key, item in attributes.items() if not key.startswith("_")},
            depth=depth + 1,
        )
    return f"<{type(value).__name__}>"


def redact_diagnostics(value: Any) -> Any:
    """Recursively redact secrets, identifiers, and location data."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            normalized = text_key.lower().replace("-", "_")
            compact = normalized.replace("_", "")
            redacted[text_key] = (
                REDACTED
                if normalized in _SENSITIVE_KEYS or compact in _SENSITIVE_COMPACT_KEYS
                else redact_diagnostics(item)
            )
        return redacted
    if isinstance(value, list):
        return [redact_diagnostics(item) for item in value]
    return value
