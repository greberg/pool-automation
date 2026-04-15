"""Sensor platform for Pool Automation."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PoolAutomationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Automation sensors."""
    coordinator: PoolAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            PoolFreeChlorineSensor(coordinator, entry),
            PoolExperimentalFCSensor(coordinator, entry),
            PoolPrioritySensor(coordinator, entry),
            PoolDosePhSensor(coordinator, entry),
            PoolDoseChlorineSensor(coordinator, entry),
            PoolHclRemainingSensor(coordinator, entry),
            PoolNacloRemainingSensor(coordinator, entry),
        ]
    )


class PoolSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Pool Automation sensors."""

    def __init__(
        self,
        coordinator: PoolAutomationCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Pool Automation",
            "model": "ESPHome Pool Kit",
        }

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}


class PoolFreeChlorineSensor(PoolSensorBase):
    """Sensor for ML-estimated free chlorine (ppm)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "free_chlorine", "Pool Free Chlorine (FC)")
        self._attr_native_unit_of_measurement = "ppm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water-check"

    @property
    def native_value(self):
        return self._data.get("experimental_fc")


class PoolExperimentalFCSensor(PoolSensorBase):
    """Sensor for calibrated free chlorine estimate."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "experimental_fc", "Pool Experimental FC")
        self._attr_native_unit_of_measurement = "ppm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:test-tube"
        self._attr_entity_registry_enabled_default = False  # hidden by default

    @property
    def native_value(self):
        return self._data.get("experimental_fc")


class PoolPrioritySensor(PoolSensorBase):
    """Sensor for current dosing priority."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "priority", "Pool Management Priority")
        self._attr_icon = "mdi:priority-high"

    @property
    def native_value(self):
        return self._data.get("priority", "unknown")

    @property
    def extra_state_attributes(self):
        data = self._data
        return {
            "ph": data.get("ph"),
            "orp": data.get("orp"),
            "free_chlorine_ppm": data.get("experimental_fc"),
            "temperature": data.get("temperature"),
        }


class PoolDosePhSensor(PoolSensorBase):
    """Sensor for calculated pH dose in mL."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "dose_ph_ml", "Pool pH Dose")
        self._attr_native_unit_of_measurement = "mL"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flask"

    @property
    def native_value(self):
        return self.coordinator.calculate_ph_dose_ml()


class PoolDoseChlorineSensor(PoolSensorBase):
    """Sensor for calculated chlorine dose in mL."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "dose_chlorine_ml", "Pool Chlorine Dose")
        self._attr_native_unit_of_measurement = "mL"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cup-water"

    @property
    def native_value(self):
        return self.coordinator.calculate_chlorine_dose_ml()


class PoolHclRemainingSensor(PoolSensorBase):
    """Sensor for remaining HCl (pH-down) tank volume."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "hcl_remaining_ml", "Pool HCl Tank Remaining")
        self._attr_native_unit_of_measurement = "mL"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flask-minus"

    @property
    def native_value(self):
        val = self._data.get("hcl_remaining_ml")
        return round(val, 0) if val is not None else None


class PoolNacloRemainingSensor(PoolSensorBase):
    """Sensor for remaining NaClO (liquid chlorine) tank volume."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "naclo_remaining_ml", "Pool NaClO Tank Remaining")
        self._attr_native_unit_of_measurement = "mL"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cup-water"

    @property
    def native_value(self):
        val = self._data.get("naclo_remaining_ml")
        return round(val, 0) if val is not None else None
