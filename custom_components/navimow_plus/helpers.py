"""Pure helpers shared by Navimow Plus entities."""

from __future__ import annotations

from typing import Any


def status_refresh_due(
    *,
    now: float,
    last_mqtt_state: float | None,
    last_http_fetch: float | None,
    mqtt_stale_seconds: float,
    http_min_interval: float,
    force: bool = False,
) -> bool:
    """Return whether an authoritative REST status refresh should run."""
    if force:
        return True
    mqtt_is_stale = (
        last_mqtt_state is None or now - last_mqtt_state > mqtt_stale_seconds
    )
    http_is_ready = last_http_fetch is None or now - last_http_fetch > http_min_interval
    return mqtt_is_stale and http_is_ready


def extract_position(position: Any) -> tuple[float, float] | None:
    """Return a validated latitude/longitude pair from known payload shapes."""
    if not isinstance(position, dict):
        return None
    latitude = position.get("latitude", position.get("lat"))
    longitude = position.get("longitude", position.get("lng", position.get("lon")))
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    if latitude == 0 and longitude == 0:
        return None
    return latitude, longitude


def error_value(state: Any, event: Any) -> str | None:
    """Prefer a current state error and otherwise expose the latest error event."""
    error = getattr(state, "error", None)
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "unknown")
    if getattr(state, "state", None) == "error":
        return "error"
    if event is not None and str(getattr(event, "level", "")).lower() == "error":
        return str(
            getattr(event, "message", None) or getattr(event, "event", "unknown")
        )
    return None
