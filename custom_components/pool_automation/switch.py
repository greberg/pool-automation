"""Switch platform for Pool Automation."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    """Set up Pool Automation switches."""
    coordinator: PoolAutomationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PoolAutomationSwitch(coordinator, entry)])


class PoolAutomationSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable automatic pool dosing."""

    def __init__(
        self,
        coordinator: PoolAutomationCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Pool Automation Mode"
        self._attr_unique_id = f"{entry.entry_id}_automation_enabled"
        self._attr_icon = "mdi:pool"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Pool Automation",
            "model": "ESPHome Pool Kit",
        }

    @property
    def is_on(self) -> bool:
        return self.coordinator.automation_enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.automation_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.automation_enabled = False
        self.async_write_ha_state()
