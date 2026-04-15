"""Button platform for Pool Automation – manual dose triggers."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PoolAutomationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Automation buttons."""
    coordinator: PoolAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PoolDosePhButton(coordinator, entry),
            PoolDoseChlorineButton(coordinator, entry),
            PoolDoseFlocButton(coordinator, entry),
            PoolResetHclTankButton(coordinator, entry),
            PoolResetNacloTankButton(coordinator, entry),
        ]
    )


class _PoolButtonBase(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry, key, name, icon):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Pool Automation",
            "model": "ESPHome Pool Kit",
        }


class PoolDosePhButton(_PoolButtonBase):
    """Button to trigger a manual pH-down dose."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "dose_ph_btn", "Pool: Dose pH Down", "mdi:arrow-down-circle")

    async def async_press(self) -> None:
        await self.coordinator.async_dose_ph()


class PoolDoseChlorineButton(_PoolButtonBase):
    """Button to trigger a manual chlorine dose."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "dose_chlorine_btn", "Pool: Dose Chlorine", "mdi:water-plus")

    async def async_press(self) -> None:
        await self.coordinator.async_dose_chlorine()


class PoolDoseFlocButton(_PoolButtonBase):
    """Button to trigger a manual flocculant dose."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "dose_floc_btn", "Pool: Dose Flocculant", "mdi:water-opacity")

    async def async_press(self) -> None:
        await self.coordinator.async_dose_floc()


class PoolResetHclTankButton(_PoolButtonBase):
    """Button to reset HCl tank remaining to the configured initial volume."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, "reset_hcl_tank", "Pool: Reset HCl Tank", "mdi:flask-plus"
        )

    async def async_press(self) -> None:
        self.coordinator.reset_hcl_tank()


class PoolResetNacloTankButton(_PoolButtonBase):
    """Button to reset NaClO tank remaining to the configured initial volume."""

    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry, "reset_naclo_tank", "Pool: Reset NaClO Tank", "mdi:cup-water"
        )

    async def async_press(self) -> None:
        self.coordinator.reset_naclo_tank()
