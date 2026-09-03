"""Sensor platform for Navimow integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NavimowCoordinator
from .entity import NavimowCoordinatorEntity
from .helpers import error_value


@dataclass(frozen=True, kw_only=True)
class NavimowSensorEntityDescription(SensorEntityDescription):
    """Describes Navimow sensor entity."""

    value_fn: Callable[[NavimowCoordinator], Any]


SENSOR_DESCRIPTIONS: tuple[NavimowSensorEntityDescription, ...] = (
    NavimowSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: (
            state.battery if (state := coordinator.get_device_state()) else None
        ),
    ),
    NavimowSensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:robot-mower-outline",
        value_fn=lambda coordinator: (
            state.state if (state := coordinator.get_device_state()) else None
        ),
    ),
    NavimowSensorEntityDescription(
        key="error",
        translation_key="error",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: (
            error_value(coordinator.get_device_state(), coordinator.get_last_event())
            or "none"
        ),
    ),
    NavimowSensorEntityDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda coordinator: (
            state.signal_strength if (state := coordinator.get_device_state()) else None
        ),
    ),
    NavimowSensorEntityDescription(
        key="data_source",
        translation_key="data_source",
        icon="mdi:cloud-sync-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.get_meta().get("last_data_source"),
    ),
    NavimowSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.get_meta().get("last_update"),
    ),
    NavimowSensorEntityDescription(
        key="map_data",
        translation_key="map_data",
        icon="mdi:map-outline",
        value_fn=lambda coordinator: coordinator.map_revision,
    ),
    NavimowSensorEntityDescription(
        key="position_x",
        translation_key="position_x",
        icon="mdi:axis-x-arrow",
        native_unit_of_measurement="m",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.position_x,
    ),
    NavimowSensorEntityDescription(
        key="position_y",
        translation_key="position_y",
        icon="mdi:axis-y-arrow",
        native_unit_of_measurement="m",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.position_y,
    ),
    NavimowSensorEntityDescription(
        key="heading",
        translation_key="heading",
        icon="mdi:compass-outline",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.heading,
    ),
    NavimowSensorEntityDescription(
        key="current_physical_zone",
        translation_key="current_physical_zone",
        icon="mdi:vector-polygon",
        value_fn=lambda coordinator: coordinator.current_physical_zone,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navimow sensors from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    devices = data["devices"]
    coordinators: dict[str, NavimowCoordinator] = data["coordinators"]

    entities: list[NavimowSensor] = []
    for device in devices:
        coordinator = coordinators[device.id]
        for description in SENSOR_DESCRIPTIONS:
            entities.append(
                NavimowSensor(
                    coordinator=coordinator,
                    entity_description=description,
                )
            )
    async_add_entities(entities)


class NavimowSensor(NavimowCoordinatorEntity, SensorEntity):
    """Representation of a Navimow sensor."""

    entity_description: NavimowSensorEntityDescription

    def __init__(
        self,
        coordinator: NavimowCoordinator,
        entity_description: NavimowSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description

        device = coordinator.device
        self._attr_unique_id = f"{DOMAIN}_{device.id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        if self.coordinator.get_device_state() is not None:
            return True
        return super().available

    @property
    def native_value(self) -> Any:
        """Return sensor value from coordinator."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose only lightweight map-card invalidation metadata."""
        if self.entity_description.key != "map_data":
            return None
        meta = self.coordinator.get_meta()
        return {
            "api_path": self.coordinator.map_api_path(),
            "map_version": self.coordinator.map_revision,
            "trail_revision": meta.get("trail_revision"),
            "private_cloud_connected": meta.get("private_cloud_connected"),
        }
