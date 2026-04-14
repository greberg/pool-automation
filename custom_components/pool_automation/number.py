"""Number platform for Pool Automation – editable set-points."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CHLORINE_TARGET,
    CONF_HCL_CONCENTRATION,
    CONF_NACLO_CONCENTRATION,
    CONF_PH_TARGET,
    CONF_POOL_VOLUME,
    DEFAULT_CHLORINE_TARGET,
    DEFAULT_HCL_CONCENTRATION,
    DEFAULT_NACLO_CONCENTRATION,
    DEFAULT_PH_TARGET,
    DEFAULT_POOL_VOLUME,
    DOMAIN,
)
from .coordinator import PoolAutomationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Automation number entities."""
    coordinator: PoolAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PoolTargetPhNumber(coordinator, entry),
            PoolTargetChlorineNumber(coordinator, entry),
            PoolVolumeNumber(coordinator, entry),
            PoolHClConcentrationNumber(coordinator, entry),
            PoolNaClOConcentrationNumber(coordinator, entry),
        ]
    )


class _PoolNumberBase(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry, key, name, icon):
        super().__init__(coordinator)
        self._entry = entry
        self._conf_key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}_number"
        self._attr_icon = icon
        self._attr_mode = NumberMode.BOX
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Pool Automation",
            "model": "ESPHome Pool Kit",
        }

    def _cfg_value(self, default):
        cfg = {**self._entry.data, **self._entry.options}
        return cfg.get(self._conf_key, default)

    async def async_set_native_value(self, value: float) -> None:
        new_options = {**self._entry.options, self._conf_key: value}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        await self.coordinator.async_request_refresh()


class PoolTargetPhNumber(_PoolNumberBase):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, CONF_PH_TARGET, "Pool Target pH", "mdi:ph")
        self._attr_native_min_value = 7.0
        self._attr_native_max_value = 7.8
        self._attr_native_step = 0.05
        self._attr_native_unit_of_measurement = "pH"

    @property
    def native_value(self):
        return self._cfg_value(DEFAULT_PH_TARGET)


class PoolTargetChlorineNumber(_PoolNumberBase):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, CONF_CHLORINE_TARGET, "Pool Target Free Chlorine", "mdi:water-check")
        self._attr_native_min_value = 0.5
        self._attr_native_max_value = 5.0
        self._attr_native_step = 0.1
        self._attr_native_unit_of_measurement = "ppm"

    @property
    def native_value(self):
        return self._cfg_value(DEFAULT_CHLORINE_TARGET)


class PoolVolumeNumber(_PoolNumberBase):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, CONF_POOL_VOLUME, "Pool Volume", "mdi:pool")
        self._attr_native_min_value = 1.0
        self._attr_native_max_value = 500.0
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = "m³"

    @property
    def native_value(self):
        return self._cfg_value(DEFAULT_POOL_VOLUME)


class PoolHClConcentrationNumber(_PoolNumberBase):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, CONF_HCL_CONCENTRATION, "Pool HCl Concentration", "mdi:flask")
        self._attr_native_min_value = 5.0
        self._attr_native_max_value = 35.0
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self):
        return self._cfg_value(DEFAULT_HCL_CONCENTRATION)


class PoolNaClOConcentrationNumber(_PoolNumberBase):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, CONF_NACLO_CONCENTRATION, "Pool NaClO Concentration", "mdi:cup-water")
        self._attr_native_min_value = 5.0
        self._attr_native_max_value = 25.0
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self):
        return self._cfg_value(DEFAULT_NACLO_CONCENTRATION)
