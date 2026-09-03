"""DataUpdateCoordinator for Navimow integration."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from mower_sdk.api import MowerAPI
from mower_sdk.errors import MowerAPIError
from mower_sdk.models import (
    Device,
    DeviceAttributesMessage,
    DeviceEventMessage,
    DeviceStateMessage,
    DeviceStatus,
)
from mower_sdk.sdk import NavimowSDK

from .const import (
    DOMAIN,
    HTTP_FALLBACK_MIN_INTERVAL,
    MAX_TRAIL_POINTS,
    MQTT_STALE_SECONDS,
    PRIVATE_MAP_POLL_INTERVAL,
    UPDATE_INTERVAL,
)
from .map_support import extract_map_geometry, resolve_map_identifiers, zone_for_point

if TYPE_CHECKING:
    from .private_cloud import PrivateCloudClient

_LOGGER = logging.getLogger(__name__)


class NavimowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Navimow data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        sdk: NavimowSDK,
        api: MowerAPI,
        device: Device,
        oauth_session: config_entry_oauth2_flow.OAuth2Session | None = None,
        entry: ConfigEntry | None = None,
        private_client: PrivateCloudClient | None = None,
        private_serial: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.sdk = sdk
        self.api = api
        self.device = device
        self.oauth_session = oauth_session
        self.entry = entry
        self.private_client = private_client
        self.private_serial = private_serial
        self.data: dict[str, Any] = {}
        self._last_state: DeviceStateMessage | None = None
        self._last_attributes: DeviceAttributesMessage | None = None
        self._last_event: DeviceEventMessage | None = None
        self._last_mqtt_update: float | None = None
        self._last_http_fetch: float | None = None
        self._last_data_source: str | None = None
        self._last_update: datetime | None = None
        self._private_connected = False
        self._private_error: str | None = None
        self._last_private_poll: float | None = None
        self._map_geometry: dict[str, Any] | None = None
        self._map_revision: str | None = None
        self._location: dict[str, Any] = {}
        self._trail: list[list[float]] = []
        self._trail_session = 0
        self._trail_active = False
        self._trail_revision = 0
        self._map_store: Store[dict[str, Any]] = Store(
            hass,
            1,
            f"{DOMAIN}.map.{device.id}",
        )

    async def async_setup(self) -> None:
        """Register callbacks from SDK."""
        self.sdk.on_state(self._handle_state)
        self.sdk.on_attributes(self._handle_attributes)
        self.sdk.on_event(self._handle_event)
        cached = await self._map_store.async_load()
        if isinstance(cached, dict):
            geometry = cached.get("geometry")
            if isinstance(geometry, dict):
                self._map_geometry = geometry
                self._map_revision = str(cached.get("revision") or "") or None

    def _build_data(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "state": self._last_state,
            "attributes": self._last_attributes,
            "event": self._last_event,
            "map": self._map_geometry,
            "location": dict(self._location),
            "meta": {
                "last_data_source": self._last_data_source,
                "last_update": self._last_update,
                "last_mqtt_update_monotonic": self._last_mqtt_update,
                "last_http_fetch_monotonic": self._last_http_fetch,
                "private_cloud_connected": self._private_connected,
                "private_cloud_error": self._private_error,
                "map_revision": self._map_revision,
                "trail_revision": self._trail_revision,
            },
        }

    async def _async_refresh_private_map(self, now: float) -> None:
        """Refresh map metadata and fetch geometry only when its revision changes."""
        if not self.private_client or not self.private_serial:
            return
        if (
            self._last_private_poll is not None
            and now - self._last_private_poll < PRIVATE_MAP_POLL_INTERVAL
        ):
            return
        self._last_private_poll = now

        def fetch() -> tuple[dict[str, Any] | None, str | None]:
            location = self.private_client.location(self.private_serial)
            maps = self.private_client.map_list(self.private_serial)
            map_id, base_id, edit_time = resolve_map_identifiers(location, maps)
            if map_id is None or base_id is None:
                return None, None
            revision = "|".join((map_id, base_id, edit_time or ""))
            if revision == self._map_revision and self._map_geometry is not None:
                return None, revision
            raw = self.private_client.map_detail(
                self.private_serial,
                map_id,
                base_id,
            )
            geometry = extract_map_geometry(raw)
            if geometry is not None:
                geometry.update(
                    {
                        "map_id": map_id,
                        "map_base_id": base_id,
                        "edit_time": edit_time,
                        "revision": revision,
                    }
                )
            return geometry, revision

        try:
            geometry, revision = await self.hass.async_add_executor_job(fetch)
            self._private_connected = True
            self._private_error = None
            if geometry is not None and revision is not None:
                self._map_geometry = geometry
                self._map_revision = revision
                await self._map_store.async_save(
                    {"geometry": geometry, "revision": revision}
                )
            elif revision is None and self._map_geometry is None:
                self._private_error = "No map identifiers returned"
        except Exception as err:  # noqa: BLE001 - preserve cached map on failure
            self._private_connected = False
            self._private_error = type(err).__name__
            _LOGGER.warning(
                "Private map refresh failed for device %s: %s",
                self.device.id,
                err,
            )

    def _device_status_to_state(self, status: DeviceStatus) -> DeviceStateMessage:
        error: dict[str, Any] | None = None
        if status.error_code and status.error_code.value != "none":
            error = {
                "code": status.error_code.value,
                "message": status.error_message,
            }
        return DeviceStateMessage(
            device_id=status.device_id,
            timestamp=status.timestamp,
            state=status.status.value,
            battery=status.battery,
            signal_strength=status.signal_strength,
            position=status.position,
            error=error,
            metrics=None,
        )

    async def _async_ensure_valid_token(self) -> str | None:
        if not self.oauth_session:
            return None
        try:
            token: dict[str, Any] | None
            if hasattr(self.oauth_session, "async_ensure_token_valid"):
                await self.oauth_session.async_ensure_token_valid()
                token = self.oauth_session.token
            elif hasattr(self.oauth_session, "async_get_valid_token"):
                token = await self.oauth_session.async_get_valid_token()
            else:
                token = self.oauth_session.token
        except ConfigEntryAuthFailed:
            # 确定性认证失败（refresh_token 缺失或被服务端拒绝）→ 直接上报，让 HA 引导用户重新认证
            raise
        except Exception as err:
            # 瞬态错误（网络超时、DNS 等）→ 不立即触发重新认证流程。
            # 尝试沿用缓存中的 access_token；若缓存也不可用才升级为认证失败。
            _LOGGER.warning(
                "Token refresh failed (likely transient), falling back to cached token: %s",
                err,
            )
            cached = getattr(self.oauth_session, "token", None)
            if cached and cached.get("access_token"):
                token = cached
            else:
                raise ConfigEntryAuthFailed(
                    f"Token refresh failed and no cached token available: {err}"
                ) from err
        if not token or not token.get("access_token"):
            raise ConfigEntryAuthFailed("No access token after refresh")
        access_token = token["access_token"]
        self.api.set_token(access_token)
        return access_token

    async def _async_update_data(self) -> dict[str, Any]:
        # 每次 update 都主动刷新 token，确保 api._token 与 oauth_session 保持同步。
        # 若仅在 HTTP fallback 时刷新，MQTT 正常推数据期间 token 长期不更新，
        # 过期后用户下发指令会立即收到 CODE_OAUTH_INFO_ILLEGAL。
        await self._async_ensure_valid_token()

        cached_state = self.sdk.get_cached_state(self.device.id)
        if cached_state is not None:
            self._last_state = cached_state
            self._last_data_source = "mqtt_cache"

        cached_attrs = self.sdk.get_cached_attributes(self.device.id)
        if cached_attrs is not None:
            self._last_attributes = cached_attrs

        now = time.monotonic()
        is_mqtt_stale = (
            self._last_mqtt_update is None
            or now - self._last_mqtt_update > MQTT_STALE_SECONDS
        )
        can_http_fetch = (
            self._last_http_fetch is None
            or now - self._last_http_fetch > HTTP_FALLBACK_MIN_INTERVAL
        )
        if is_mqtt_stale and can_http_fetch:
            try:
                status = await self.api.async_get_device_status(self.device.id)
                self._last_state = self._device_status_to_state(status)
                if self._last_state.state != "error" and not self._last_state.error:
                    self._last_event = None
                self._last_http_fetch = now
                self._last_data_source = "http_fallback"
                self._last_update = datetime.now(timezone.utc)
            except ConfigEntryAuthFailed:
                raise
            except MowerAPIError as err:
                _LOGGER.warning(
                    "HTTP fallback failed for device %s: %s", self.device.id, err
                )

        await self._async_refresh_private_map(now)

        _LOGGER.debug(
            "Coordinator update: device=%s source=%s mqtt_ts=%s http_ts=%s",
            self.device.id,
            self._last_data_source,
            self._last_mqtt_update,
            self._last_http_fetch,
        )
        self.data = self._build_data()
        return self.data

    def _handle_state(self, state: DeviceStateMessage) -> None:
        if state.device_id != self.device.id:
            return
        _LOGGER.debug(
            "MQTT state received: device=%s state=%s battery=%s",
            state.device_id,
            state.state,
            state.battery,
        )
        self._last_mqtt_update = time.monotonic()
        self._last_data_source = "mqtt_push"
        self._last_update = datetime.now(timezone.utc)
        self.hass.loop.call_soon_threadsafe(self._update_from_state, state)

    def _handle_attributes(self, attrs: DeviceAttributesMessage) -> None:
        if attrs.device_id != self.device.id:
            return
        _LOGGER.debug(
            "MQTT attributes received: device=%s keys=%d",
            attrs.device_id,
            len(getattr(attrs, "__dict__", {}) or {}),
        )
        self._last_mqtt_update = time.monotonic()
        self._last_update = datetime.now(timezone.utc)
        self.hass.loop.call_soon_threadsafe(self._update_from_attributes, attrs)

    def _handle_event(self, event: DeviceEventMessage) -> None:
        if event.device_id != self.device.id:
            return
        self._last_mqtt_update = time.monotonic()
        self._last_update = datetime.now(timezone.utc)
        self.hass.loop.call_soon_threadsafe(self._update_from_event, event)

    def _update_from_state(self, state: DeviceStateMessage) -> None:
        self._last_state = state
        if state.state != "error" and not state.error:
            self._last_event = None
        self._last_data_source = "mqtt_push"
        self.async_set_updated_data(self._build_data())

    def _update_from_attributes(self, attrs: DeviceAttributesMessage) -> None:
        self._last_attributes = attrs
        self.async_set_updated_data(self._build_data())

    def _update_from_event(self, event: DeviceEventMessage) -> None:
        self._last_event = event
        self._last_data_source = "mqtt_push"
        self.async_set_updated_data(self._build_data())

    def get_device_state(self) -> DeviceStateMessage | None:
        return self.data.get("state")

    def get_device_attributes(self) -> DeviceAttributesMessage | None:
        return self.data.get("attributes")

    def get_device_info(self) -> Any | None:
        return self.data.get("device")

    def get_last_event(self) -> DeviceEventMessage | None:
        return self.data.get("event")

    def get_meta(self) -> dict[str, Any]:
        return self.data.get("meta", {})

    def ingest_mqtt_location(self, location: dict[str, Any]) -> None:
        """Ingest a decoded official MQTT location message on the HA loop."""
        self._location = dict(location)
        if location.get("pose_updated"):
            x = location.get("x")
            y = location.get("y")
            try:
                point = [float(x), float(y)]
            except (TypeError, ValueError):
                point = []
            raw_state = str(location.get("vehicle_state") or "")
            state = self._last_state.state if self._last_state is not None else ""
            active = raw_state in {"isRunning", "isMapping"} or state == "mowing"
            if active and point:
                if not self._trail_active:
                    self._trail = []
                    self._trail_session += 1
                if not self._trail or self._trail[-1] != point:
                    self._trail.append(point)
                    self._trail = self._trail[-MAX_TRAIL_POINTS:]
                    self._trail_revision += 1
                self._trail_active = True
            elif raw_state and raw_state not in {"isRunning", "isMapping"}:
                self._trail_active = False
        self._last_mqtt_update = time.monotonic()
        self._last_data_source = "mqtt_location"
        self._last_update = datetime.now(timezone.utc)
        self.async_set_updated_data(self._build_data())

    def map_api_path(self) -> str:
        """Return this mower's authenticated map endpoint."""
        entry_id = self.entry.entry_id if self.entry is not None else ""
        return f"/api/{DOMAIN}/map/{entry_id}/{self.device.id}"

    def map_payload(self) -> dict[str, Any]:
        """Return a Navimower Map Card compatible cached payload."""
        zone = zone_for_point(
            self.position_x,
            self.position_y,
            list((self._map_geometry or {}).get("zones") or []),
        )
        state = self._last_state.state if self._last_state is not None else None
        return {
            "schema_version": 1,
            "map": self._map_geometry or {},
            "map_version": self._map_revision,
            "trail": list(self._trail),
            "trail_segments": [list(self._trail)] if len(self._trail) >= 2 else [],
            "trail_session": self._trail_session,
            "trail_revision": self._trail_revision,
            "trail_active": self._trail_active,
            "activity": state,
            "current_physical_zone": zone.get("name") if zone else None,
            "coverage": {"zones": []},
        }

    @property
    def position_x(self) -> float | None:
        value = self._location.get("x")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def position_y(self) -> float | None:
        value = self._location.get("y")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def heading(self) -> float | None:
        value = self._location.get("heading")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def current_physical_zone(self) -> str | None:
        zone = zone_for_point(
            self.position_x,
            self.position_y,
            list((self._map_geometry or {}).get("zones") or []),
        )
        return str(zone.get("name")) if zone else None

    @property
    def map_revision(self) -> str | None:
        return self._map_revision
