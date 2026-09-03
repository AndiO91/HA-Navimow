"""Diagnostic binary sensors for Navimow Plus."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import NavimowCoordinatorEntity
from .helpers import error_value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for device in data["devices"]:
        coordinator = data["coordinators"][device.id]
        entities.extend(
            (NavimowMqttConnection(coordinator), NavimowProblem(coordinator))
        )
        if coordinator.private_client is not None:
            entities.append(NavimowPrivateCloudConnection(coordinator))
    async_add_entities(entities)


class NavimowMqttConnection(NavimowCoordinatorEntity, BinarySensorEntity):
    _attr_translation_key = "mqtt_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device.id}_mqtt_connection"

    @property
    def is_on(self) -> bool:
        return self.coordinator.sdk.is_connected


class NavimowProblem(NavimowCoordinatorEntity, BinarySensorEntity):
    _attr_translation_key = "problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device.id}_problem"

    @property
    def is_on(self) -> bool:
        return (
            error_value(
                self.coordinator.get_device_state(), self.coordinator.get_last_event()
            )
            is not None
        )


class NavimowPrivateCloudConnection(NavimowCoordinatorEntity, BinarySensorEntity):
    """Report whether the optional map-cloud session is healthy."""

    _attr_translation_key = "private_cloud_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.device.id}_private_cloud_connection"
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.get_meta().get("private_cloud_connected"))

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        error = self.coordinator.get_meta().get("private_cloud_error")
        return {"error": str(error)} if error else None
