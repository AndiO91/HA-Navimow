"""GPS device tracker platform for Navimow Plus."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import NavimowCoordinatorEntity
from .helpers import extract_position


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        NavimowLocation(data["coordinators"][device.id]) for device in data["devices"]
    )


class NavimowLocation(NavimowCoordinatorEntity, TrackerEntity):
    """Expose the mower position when supplied by the Navimow cloud."""

    _attr_translation_key = "location"
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device.id}_location"

    def _position(self) -> tuple[float, float] | None:
        state = self.coordinator.get_device_state()
        return extract_position(state.position if state else None)

    @property
    def latitude(self) -> float | None:
        return position[0] if (position := self._position()) else None

    @property
    def longitude(self) -> float | None:
        return position[1] if (position := self._position()) else None

    @property
    def available(self) -> bool:
        return self._position() is not None and super().available
