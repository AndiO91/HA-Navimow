"""DataUpdateCoordinator for Navimow integration."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
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
    ACTIVE_STATUS_POLL_INTERVAL,
    DOMAIN,
    HTTP_FALLBACK_MIN_INTERVAL,
    MQTT_STALE_SECONDS,
    RETURNING_STATUS_POLL_INTERVAL,
    UPDATE_INTERVAL,
)
from .helpers import status_refresh_due

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
        self.data: dict[str, Any] = {}
        self._last_state: DeviceStateMessage | None = None
        self._last_attributes: DeviceAttributesMessage | None = None
        self._last_event: DeviceEventMessage | None = None
        self._last_mqtt_update: float | None = None
        self._last_http_fetch: float | None = None
        self._last_data_source: str | None = None
        self._last_update: datetime | None = None
        self._force_http_refresh = False
        self._force_http_after: float | None = None
        self._force_http_expected_states: frozenset[str] = frozenset()

    async def async_setup(self) -> None:
        """Register callbacks from SDK."""
        self.sdk.on_state(self._handle_state)
        self.sdk.on_attributes(self._handle_attributes)
        self.sdk.on_event(self._handle_event)

    def _build_data(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "state": self._last_state,
            "attributes": self._last_attributes,
            "event": self._last_event,
            "meta": {
                "last_data_source": self._last_data_source,
                "last_update": self._last_update,
                "last_mqtt_update_monotonic": self._last_mqtt_update,
                "last_http_fetch_monotonic": self._last_http_fetch,
            },
        }

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

        # The SDK cache contains the last MQTT object, not a new observation.
        # Use it only to seed an empty coordinator; replaying it every 30 seconds
        # can overwrite a newer REST result and makes stale data look fresh.
        if self._last_state is None:
            cached_state = self.sdk.get_cached_state(self.device.id)
            if cached_state is not None:
                self._last_state = cached_state
                self._last_data_source = "mqtt_cache_initial"

        if self._last_attributes is None:
            cached_attrs = self.sdk.get_cached_attributes(self.device.id)
            if cached_attrs is not None:
                self._last_attributes = cached_attrs

        now = time.monotonic()
        confirming_mqtt_push = (
            self._force_http_refresh
            and self._force_http_after is not None
            and self._last_mqtt_update is not None
            and self._last_mqtt_update >= self._force_http_after
            and self._last_state is not None
            and self._last_state.state in self._force_http_expected_states
        )
        if confirming_mqtt_push:
            self._force_http_refresh = False
            self._force_http_after = None
            self._force_http_expected_states = frozenset()

        current_state = self._last_state.state if self._last_state is not None else None
        state_poll_interval = None
        if current_state == "returning":
            state_poll_interval = RETURNING_STATUS_POLL_INTERVAL
        elif current_state in {"mowing", "paused"}:
            state_poll_interval = ACTIVE_STATUS_POLL_INTERVAL
        status_observations = [
            timestamp
            for timestamp in (self._last_mqtt_update, self._last_http_fetch)
            if timestamp is not None
        ]
        active_poll_due = bool(
            state_poll_interval is not None
            and (
                not status_observations
                or now - max(status_observations) >= state_poll_interval
            )
        )
        if status_refresh_due(
            now=now,
            last_mqtt_state=self._last_mqtt_update,
            last_http_fetch=self._last_http_fetch,
            mqtt_stale_seconds=MQTT_STALE_SECONDS,
            http_min_interval=HTTP_FALLBACK_MIN_INTERVAL,
            state_poll_interval=state_poll_interval,
            force=self._force_http_refresh,
        ):
            mqtt_marker = self._last_mqtt_update
            forced_refresh = self._force_http_refresh
            try:
                # Throttle failed requests as well as successful ones.
                self._last_http_fetch = now
                status = await self.api.async_get_device_status(self.device.id)
                # A state push received while REST was in flight is newer than
                # the REST snapshot and must win the race.
                if self._last_mqtt_update == mqtt_marker:
                    self._last_state = self._device_status_to_state(status)
                    if self._last_state.state != "error" and not self._last_state.error:
                        self._last_event = None
                    if forced_refresh:
                        self._last_data_source = "http_command_refresh"
                    elif active_poll_due:
                        self._last_data_source = "http_active_poll"
                    else:
                        self._last_data_source = "http_fallback"
                    self._last_update = datetime.now(timezone.utc)
                self._force_http_refresh = False
                self._force_http_after = None
                self._force_http_expected_states = frozenset()
            except ConfigEntryAuthFailed:
                raise
            except MowerAPIError as err:
                _LOGGER.warning(
                    "HTTP fallback failed for device %s: %s", self.device.id, err
                )

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
        self._last_update = datetime.now(timezone.utc)
        self.hass.loop.call_soon_threadsafe(self._update_from_attributes, attrs)

    def _handle_event(self, event: DeviceEventMessage) -> None:
        if event.device_id != self.device.id:
            return
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

    async def async_refresh_after_command(
        self,
        command_started: float,
        expected_states: frozenset[str],
    ) -> bool:
        """Confirm a command via a new MQTT push or a forced REST request."""
        if (
            self._last_mqtt_update is not None
            and self._last_mqtt_update >= command_started
            and self._last_state is not None
            and self._last_state.state in expected_states
        ):
            return True
        self._force_http_refresh = True
        self._force_http_after = command_started
        self._force_http_expected_states = expected_states
        await self.async_request_refresh()
        return bool(
            self._last_state is not None and self._last_state.state in expected_states
        )
