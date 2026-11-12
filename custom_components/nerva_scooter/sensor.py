"""Sensori Nerva Scooter."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE, UnitOfElectricCurrent, UnitOfLength, UnitOfPower, UnitOfSpeed, UnitOfTemperature,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

M = SensorStateClass.MEASUREMENT
T = SensorDeviceClass.TEMPERATURE
C = UnitOfTemperature.CELSIUS
SENSORS = [
    SensorEntityDescription("soc", name="Batteria", device_class=SensorDeviceClass.BATTERY, native_unit_of_measurement=PERCENTAGE, state_class=M),
    SensorEntityDescription("soh", name="Salute batteria", native_unit_of_measurement=PERCENTAGE, state_class=M, icon="mdi:battery-heart-variant"),
    SensorEntityDescription("battery_temp", name="Temperatura batteria", device_class=T, native_unit_of_measurement=C, state_class=M),
    SensorEntityDescription("motor_temp", name="Temperatura motore", device_class=T, native_unit_of_measurement=C, state_class=M),
    SensorEntityDescription("vcu_temp", name="Temperatura VCU", device_class=T, native_unit_of_measurement=C, state_class=M, entity_registry_enabled_default=False),
    SensorEntityDescription("vehicle_temp", name="Temperatura veicolo", device_class=T, native_unit_of_measurement=C, state_class=M, entity_registry_enabled_default=False),
    SensorEntityDescription("last20_consumption", name="Consumo ultimi 20 km", state_class=M, icon="mdi:gauge", entity_registry_enabled_default=False),
    SensorEntityDescription("mcu_temp", name="Temperatura centralina", device_class=T, native_unit_of_measurement=C, state_class=M),
    SensorEntityDescription("battery_current", name="Corrente batteria", device_class=SensorDeviceClass.CURRENT, native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=M),
    SensorEntityDescription("speed", name="Velocità", device_class=SensorDeviceClass.SPEED, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR, state_class=M),
    SensorEntityDescription("power", name="Potenza", native_unit_of_measurement=UnitOfPower.KILO_WATT, state_class=M, icon="mdi:flash"),
    SensorEntityDescription("odometer", name="Chilometri totali", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=UnitOfLength.KILOMETERS, state_class=SensorStateClass.TOTAL_INCREASING),
    SensorEntityDescription("range", name="Autonomia", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=UnitOfLength.KILOMETERS, state_class=M),
    SensorEntityDescription("avg_consumption", name="Consumo medio", state_class=M, icon="mdi:gauge"),
    SensorEntityDescription("bms_limit_charge_current", name="Limite corrente ricarica", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=M, entity_registry_enabled_default=False),
    SensorEntityDescription("bms_limit_discharge_current", name="Limite corrente scarica", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=M, entity_registry_enabled_default=False),
    *[
        SensorEntityDescription(k, name=f"Codice guasto {n}", icon="mdi:alert-circle-outline", entity_registry_enabled_default=False)
        for k, n in [("bms_fault", "BMS"), ("mcu_fault", "motore"), ("vcu_fault", "VCU"), ("abs_fault", "ABS"), ("obc_fault", "caricatore"), ("dcdc_fault", "DC/DC"), ("display_fault", "display")]
    ],
]


async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NervaSensor(coord, entry, d) for d in SENSORS)


class NervaSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coord, entry, desc) -> None:
        super().__init__(coord)
        self.entity_description = desc
        self._attr_unique_id = f"{entry.unique_id}_{desc.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)}, name="Scooter Nerva", manufacturer="Nerva",
        )

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)
