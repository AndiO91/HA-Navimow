"""Authenticated map endpoint consumed by Navimower-compatible dashboard cards."""

from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_REGISTERED = f"{DOMAIN}_map_api_registered"


class NavimowPlusMapView(HomeAssistantView):
    """Return cached geometry and live pose without making a cloud request."""

    url = "/api/navimow_plus/map/{entry_id}/{device_id}"
    name = "api:navimow_plus:map"
    requires_auth = True

    async def get(
        self,
        request: web.Request,
        entry_id: str,
        device_id: str,
    ) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entry_data = (hass.data.get(DOMAIN) or {}).get(entry_id)
        coordinator = (
            (entry_data.get("coordinators") or {}).get(device_id)
            if isinstance(entry_data, dict)
            else None
        )
        if coordinator is None:
            raise web.HTTPNotFound(text="Unknown Navimow Plus mower")
        return self.json(coordinator.map_payload())


def async_register_map_api(hass: HomeAssistant) -> None:
    """Register the authenticated HTTP view exactly once."""
    if hass.data.get(_REGISTERED):
        return
    hass.http.register_view(NavimowPlusMapView)
    hass.data[_REGISTERED] = True
