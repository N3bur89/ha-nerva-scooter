"""Sensore binario stato connessione Nerva Scooter."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NervaConnectedBinarySensor(coord, entry)])


class NervaConnectedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Connesso"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coord, entry) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{entry.unique_id}_connected"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="Scooter Nerva",
            manufacturer="Nerva",
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected
