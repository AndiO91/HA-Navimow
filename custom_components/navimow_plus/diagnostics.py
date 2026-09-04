"""Diagnostics support for Navimow Plus."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .diagnostics_helpers import REDACTED, diagnostics_value, redact_diagnostics


def _coordinator_diagnostics(coordinator: Any) -> dict[str, Any]:
    """Return privacy-safe runtime diagnostics for one mower."""
    now = time.monotonic()
    meta = coordinator.get_meta()
    last_mqtt = meta.get("last_mqtt_update_monotonic")
    last_http = meta.get("last_http_fetch_monotonic")
    device = coordinator.get_device_info()

    result = {
        "device": {
            "device_id": getattr(device, "id", None),
            "name": getattr(device, "name", None),
            "model": getattr(device, "model", None),
            "firmware_version": getattr(device, "firmware_version", None),
            "serial_number": getattr(device, "serial_number", None),
        },
        "connection": {
            "mqtt_connected": bool(coordinator.sdk.is_connected),
            "last_update_success": coordinator.last_update_success,
            "last_data_source": meta.get("last_data_source"),
            "last_update": meta.get("last_update"),
            "mqtt_state_age_seconds": (
                round(max(0.0, now - last_mqtt), 1)
                if isinstance(last_mqtt, (int, float))
                else None
            ),
            "http_fetch_age_seconds": (
                round(max(0.0, now - last_http), 1)
                if isinstance(last_http, (int, float))
                else None
            ),
        },
        "state": coordinator.get_device_state(),
        "attributes": coordinator.get_device_attributes(),
        "last_event": coordinator.get_last_event(),
    }
    return redact_diagnostics(diagnostics_value(result))


async def _integration_version(hass: HomeAssistant) -> str | None:
    """Return the loaded custom integration version."""
    integration = await async_get_integration(hass, DOMAIN)
    return integration.version


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Navimow Plus config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinators = runtime["coordinators"]
    return {
        "integration": {
            "domain": DOMAIN,
            "version": await _integration_version(hass),
        },
        "config_entry": redact_diagnostics(diagnostics_value(entry.as_dict())),
        "mowers": [
            _coordinator_diagnostics(coordinator)
            for coordinator in coordinators.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for one Navimow mower device."""
    mower_id = next(
        (
            identifier
            for domain, identifier in device.identifiers
            if domain == DOMAIN
        ),
        None,
    )
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinators"].get(mower_id)
    if coordinator is None:
        return {
            "integration": {
                "domain": DOMAIN,
                "version": await _integration_version(hass),
            },
            "device_id": REDACTED,
            "error": "No active coordinator found for this device",
        }
    return {
        "integration": {
            "domain": DOMAIN,
            "version": await _integration_version(hass),
        },
        "mower": _coordinator_diagnostics(coordinator),
    }
