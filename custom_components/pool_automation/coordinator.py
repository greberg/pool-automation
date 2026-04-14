"""Coordinator for Pool Automation integration."""
from __future__ import annotations

import logging
import math
from datetime import timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CHLORINE_GRAMS_PER_10K_L_PER_PPM,
    CHLORINE_LIQUID_DENSITY,
    CONF_BUTTON_DOSE_CHLORINE,
    CONF_BUTTON_DOSE_FLOC,
    CONF_BUTTON_DOSE_PH,
    CONF_CHLORINE_MAX,
    CONF_CHLORINE_MIN,
    CONF_CHLORINE_TARGET,
    CONF_ENABLE_FLOC,
    CONF_FLOC_DURATION,
    CONF_FLOC_VOLUME,
    CONF_HCL_CONCENTRATION,
    CONF_MIN_CIRCULATION,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_NACLO_CONCENTRATION,
    CONF_NUMBER_DURATION_FLOC,
    CONF_NUMBER_VOLUME_CHLORINE,
    CONF_NUMBER_VOLUME_FLOC,
    CONF_NUMBER_VOLUME_PH,
    CONF_PH_MAX,
    CONF_PH_MIN,
    CONF_PH_TARGET,
    CONF_POOL_VOLUME,
    CONF_SENSOR_CIRCULATION,
    CONF_SENSOR_ORP,
    CONF_SENSOR_PH,
    CONF_SENSOR_TEMP,
    CONF_TIMER_CHEMICALS,
    COORDINATOR_UPDATE_INTERVAL,
    DEFAULT_CHLORINE_MAX,
    DEFAULT_CHLORINE_MIN,
    DEFAULT_CHLORINE_TARGET,
    DEFAULT_ENABLE_FLOC,
    DEFAULT_FLOC_DURATION,
    DEFAULT_FLOC_VOLUME,
    DEFAULT_HCL_CONCENTRATION,
    DEFAULT_MIN_CIRCULATION,
    DEFAULT_NACLO_CONCENTRATION,
    DEFAULT_PH_MAX,
    DEFAULT_PH_MIN,
    DEFAULT_PH_TARGET,
    DEFAULT_POOL_VOLUME,
    DOMAIN,
    FC_ORP_BASE,
    FC_PH_FACTOR,
    FC_PH_REFERENCE,
    FC_SLOPE,
    PRIORITY_CHLORINE_HIGH,
    PRIORITY_CHLORINE_LOW,
    PRIORITY_OK,
    PRIORITY_PH_HIGH,
    PRIORITY_PH_LOW,
    TOPIC_ADD_CHLORINE,
    TOPIC_ADD_PH,
    TOPIC_CALC_CHLORINE,
    TOPIC_CALC_PH,
    TOPIC_EXPERIMENT_FC,
    TOPIC_FC,
    TOPIC_ORP_PH,
    TOPIC_PRIORITY,
    TOPIC_RECOMMENDED_PRIORITY,
)

_LOGGER = logging.getLogger(__name__)


class PoolAutomationCoordinator(DataUpdateCoordinator):
    """Manage pool automation state and MQTT communication."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )
        self.entry = entry
        self._subscriptions: list[Any] = []

        # Live state
        self.ph: float | None = None
        self.orp: float | None = None
        self.temperature: float | None = None
        self.free_chlorine: float | None = None
        self.experimental_fc: float | None = None
        self.priority: str = PRIORITY_OK
        self.dose_ph_ml: float | None = None
        self.dose_chlorine_ml: float | None = None
        self.automation_enabled: bool = True

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    @property
    def cfg(self) -> dict:
        """Return merged config + options."""
        return {**self.entry.data, **self.entry.options}

    def _topic(self, suffix: str) -> str:
        prefix = self.cfg.get(CONF_MQTT_TOPIC_PREFIX, "pool")
        return f"{prefix}/{suffix}"

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Subscribe to MQTT topics."""
        subscribe = mqtt.async_subscribe

        self._subscriptions.append(
            await subscribe(
                self.hass,
                self._topic(TOPIC_ORP_PH),
                self._handle_orp_ph,
            )
        )
        self._subscriptions.append(
            await subscribe(
                self.hass,
                self._topic(TOPIC_ADD_PH),
                self._handle_add_ph,
            )
        )
        self._subscriptions.append(
            await subscribe(
                self.hass,
                self._topic(TOPIC_ADD_CHLORINE),
                self._handle_add_chlorine,
            )
        )
        self._subscriptions.append(
            await subscribe(
                self.hass,
                self._topic(TOPIC_RECOMMENDED_PRIORITY),
                self._handle_recommended_priority,
            )
        )
        _LOGGER.info("Pool Automation: MQTT subscriptions active")

    async def async_unload(self) -> None:
        """Unsubscribe from MQTT."""
        for unsub in self._subscriptions:
            unsub()
        self._subscriptions.clear()

    # ------------------------------------------------------------------
    # MQTT inbound handlers
    # ------------------------------------------------------------------
    @callback
    def _handle_orp_ph(self, msg: mqtt.ReceiveMessage) -> None:
        payload = msg.payload
        try:
            orp_str, ph_str = payload.split(",")
            if "unavailable" in (orp_str, ph_str):
                _LOGGER.warning("Unavailable ORP/pH values: %s", payload)
                return
            self.orp = float(orp_str.strip())
            self.ph = float(ph_str.strip())
            self.free_chlorine = None  # will be set after ML estimate below
            self._update_fc_estimate()
            self._update_priority()
            self.async_set_updated_data(self._build_data())
        except Exception as err:
            _LOGGER.error("Error parsing pool/orpph: %s – %s", payload, err)

    @callback
    def _handle_add_ph(self, msg: mqtt.ReceiveMessage) -> None:
        try:
            self.dose_ph_ml = float(msg.payload)
            self.async_set_updated_data(self._build_data())
        except ValueError:
            _LOGGER.error("Bad add_ph payload: %s", msg.payload)

    @callback
    def _handle_add_chlorine(self, msg: mqtt.ReceiveMessage) -> None:
        try:
            self.dose_chlorine_ml = float(msg.payload)
            self.async_set_updated_data(self._build_data())
        except ValueError:
            _LOGGER.error("Bad add_chlorine payload: %s", msg.payload)

    @callback
    def _handle_recommended_priority(self, msg: mqtt.ReceiveMessage) -> None:
        self.priority = msg.payload.strip()
        self.async_set_updated_data(self._build_data())

    # ------------------------------------------------------------------
    # Chemistry calculations (pure Python – no external ML dep needed)
    # ------------------------------------------------------------------
    def _update_fc_estimate(self) -> None:
        """Estimate free chlorine from ORP and pH using calibrated formula."""
        if self.orp is None or self.ph is None:
            return
        try:
            ph_offset = FC_ORP_BASE + FC_PH_FACTOR * (self.ph - FC_PH_REFERENCE)
            exponent = (self.orp - ph_offset) / FC_SLOPE
            self.experimental_fc = round(10**exponent, 3)
        except Exception as err:
            _LOGGER.error("FC estimation error: %s", err)

    def _update_priority(self) -> None:
        """Determine dosing priority based on current pH and FC."""
        if self.ph is None or self.experimental_fc is None:
            return

        ph_min = self.cfg.get(CONF_PH_MIN, DEFAULT_PH_MIN)
        ph_max = self.cfg.get(CONF_PH_MAX, DEFAULT_PH_MAX)
        cl_min = self.cfg.get(CONF_CHLORINE_MIN, DEFAULT_CHLORINE_MIN)
        cl_max = self.cfg.get(CONF_CHLORINE_MAX, DEFAULT_CHLORINE_MAX)

        if self.ph < ph_min:
            self.priority = PRIORITY_PH_LOW
        elif self.ph > ph_max:
            self.priority = PRIORITY_PH_HIGH
        elif ph_min <= self.ph <= ph_max:
            if self.experimental_fc < cl_min:
                self.priority = PRIORITY_CHLORINE_LOW
            elif self.experimental_fc > cl_max:
                self.priority = PRIORITY_CHLORINE_HIGH
            else:
                self.priority = PRIORITY_OK
        else:
            self.priority = PRIORITY_OK

    def calculate_ph_dose_ml(self) -> float | None:
        """Calculate mL of HCl needed to reach target pH."""
        if self.ph is None:
            return None
        volume_m3 = self.cfg.get(CONF_POOL_VOLUME, DEFAULT_POOL_VOLUME)
        target_ph = self.cfg.get(CONF_PH_TARGET, DEFAULT_PH_TARGET)
        concentration = self.cfg.get(CONF_HCL_CONCENTRATION, DEFAULT_HCL_CONCENTRATION)

        gallons = volume_m3 * 264.172
        ph_change = abs(target_ph - self.ph)
        if ph_change < 0.01:
            return 0.0
        acid_strength = concentration / 15.0
        oz = (gallons / 10000) * (ph_change / 0.1) * (10 * acid_strength)
        return round(oz * 29.5735, 2)

    def calculate_chlorine_dose_ml(self) -> float | None:
        """Calculate mL of NaClO needed to reach target free chlorine."""
        if self.experimental_fc is None:
            return None
        volume_m3 = self.cfg.get(CONF_POOL_VOLUME, DEFAULT_POOL_VOLUME)
        target_ppm = self.cfg.get(CONF_CHLORINE_TARGET, DEFAULT_CHLORINE_TARGET)
        strength = self.cfg.get(CONF_NACLO_CONCENTRATION, DEFAULT_NACLO_CONCENTRATION)

        ppm_diff = target_ppm - self.experimental_fc
        if ppm_diff <= 0:
            return 0.0
        pool_liters = volume_m3 * 1000
        strength_factor = strength / 100.0
        grams = (pool_liters / 10000) * (CHLORINE_GRAMS_PER_10K_L_PER_PPM / strength_factor) * ppm_diff
        return round(grams / CHLORINE_LIQUID_DENSITY, 2)

    # ------------------------------------------------------------------
    # Actions triggered from HA (buttons / services)
    # ------------------------------------------------------------------
    async def async_dose_ph(self) -> None:
        """Trigger a pH-down dose via ESPHome."""
        ml = self.calculate_ph_dose_ml()
        if ml is None or ml <= 0:
            _LOGGER.warning("No pH dose needed or sensors unavailable.")
            return

        number_entity = self.cfg.get(CONF_NUMBER_VOLUME_PH)
        button_entity = self.cfg.get(CONF_BUTTON_DOSE_PH)

        if number_entity:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": number_entity, "value": ml},
                blocking=True,
            )

        if button_entity:
            await self.hass.services.async_call(
                "button", "press",
                {"entity_id": button_entity},
                blocking=True,
            )

        _LOGGER.info("pH dose triggered: %.2f mL", ml)

    async def async_dose_chlorine(self) -> None:
        """Trigger a chlorine dose via ESPHome."""
        ml = self.calculate_chlorine_dose_ml()
        if ml is None or ml <= 0:
            _LOGGER.warning("No chlorine dose needed or sensors unavailable.")
            return

        number_entity = self.cfg.get(CONF_NUMBER_VOLUME_CHLORINE)
        button_entity = self.cfg.get(CONF_BUTTON_DOSE_CHLORINE)

        if number_entity:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": number_entity, "value": ml},
                blocking=True,
            )

        if button_entity:
            await self.hass.services.async_call(
                "button", "press",
                {"entity_id": button_entity},
                blocking=True,
            )

        _LOGGER.info("Chlorine dose triggered: %.2f mL", ml)

    async def async_dose_floc(self) -> None:
        """Trigger a flocculant dose via ESPHome."""
        if not self.cfg.get(CONF_ENABLE_FLOC, DEFAULT_ENABLE_FLOC):
            return

        vol = self.cfg.get(CONF_FLOC_VOLUME, DEFAULT_FLOC_VOLUME)
        dur = self.cfg.get(CONF_FLOC_DURATION, DEFAULT_FLOC_DURATION)
        num_vol = self.cfg.get(CONF_NUMBER_VOLUME_FLOC)
        num_dur = self.cfg.get(CONF_NUMBER_DURATION_FLOC)
        btn = self.cfg.get(CONF_BUTTON_DOSE_FLOC)

        if num_vol:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": num_vol, "value": vol},
                blocking=True,
            )
        if num_dur:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": num_dur, "value": dur},
                blocking=True,
            )
        if btn:
            await self.hass.services.async_call(
                "button", "press",
                {"entity_id": btn},
                blocking=True,
            )
        _LOGGER.info("Flocculant dose triggered: %.1f mL for %ds", vol, dur)

    async def async_publish_orp_ph(self) -> None:
        """Publish current ORP and pH to MQTT (for external consumers)."""
        if self.orp is None or self.ph is None:
            return
        payload = f"{self.orp},{self.ph}"
        await mqtt.async_publish(
            self.hass,
            self._topic(TOPIC_ORP_PH),
            payload,
        )

    # ------------------------------------------------------------------
    # Data snapshot
    # ------------------------------------------------------------------
    def _build_data(self) -> dict:
        return {
            "ph": self.ph,
            "orp": self.orp,
            "temperature": self.temperature,
            "free_chlorine": self.free_chlorine,
            "experimental_fc": self.experimental_fc,
            "priority": self.priority,
            "dose_ph_ml": self.dose_ph_ml,
            "dose_chlorine_ml": self.dose_chlorine_ml,
            "automation_enabled": self.automation_enabled,
        }

    async def _async_update_data(self) -> dict:
        """Periodic update – recalculate from latest sensor values."""
        ph_entity = self.cfg.get(CONF_SENSOR_PH)
        orp_entity = self.cfg.get(CONF_SENSOR_ORP)
        temp_entity = self.cfg.get(CONF_SENSOR_TEMP)

        def _state_float(entity_id: str | None) -> float | None:
            if not entity_id:
                return None
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown", ""):
                return None
            try:
                return float(state.state)
            except ValueError:
                return None

        self.ph = _state_float(ph_entity)
        self.orp = _state_float(orp_entity)
        self.temperature = _state_float(temp_entity)

        if self.ph is not None and self.orp is not None:
            self._update_fc_estimate()
            self._update_priority()

        return self._build_data()
