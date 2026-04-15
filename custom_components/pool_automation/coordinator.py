"""Coordinator for Pool Automation integration – v3.

v3 changes vs v2
----------------
* Hourly dosing loop moved from YAML automations into the coordinator
  (`async_run_dosing_cycle` scheduled via `async_track_time_interval`).
* Single `_safe_to_dose()` method replaces duplicated YAML conditions.
* Tank volume tracking via `async_track_state_change_event` on pump binary
  sensors; state persisted across restarts with `homeassistant.helpers.storage`.
* HA events (`pool_automation_dosing_started` / `pool_automation_dosing_skipped`)
  let YAML automations send push notifications without coupling delivery
  channel to component logic.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CHLORINE_GRAMS_PER_10K_L_PER_PPM,
    CHLORINE_LIQUID_DENSITY,
    CONF_BINARY_PUMP_CHLORINE,
    CONF_BINARY_PUMP_PH,
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
    CONF_SENSOR_DOSED_CHLORINE,
    CONF_SENSOR_DOSED_PH,
    CONF_SENSOR_ORP,
    CONF_SENSOR_PH,
    CONF_SENSOR_TEMP,
    CONF_TANK_HCL_INITIAL,
    CONF_TANK_NACLO_INITIAL,
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
    DEFAULT_TANK_HCL_INITIAL,
    DEFAULT_TANK_NACLO_INITIAL,
    DOMAIN,
    DOSING_INTERVAL_SECONDS,
    EVENT_DOSING_SKIPPED,
    EVENT_DOSING_STARTED,
    FC_ORP_BASE,
    FC_PH_FACTOR,
    FC_PH_REFERENCE,
    FC_SLOPE,
    PRIORITY_CHLORINE_HIGH,
    PRIORITY_CHLORINE_LOW,
    PRIORITY_OK,
    PRIORITY_PH_HIGH,
    PRIORITY_PH_LOW,
    STORE_KEY,
    STORE_VERSION,
    TOPIC_ADD_CHLORINE,
    TOPIC_ADD_PH,
    TOPIC_ORP_PH,
    TOPIC_RECOMMENDED_PRIORITY,
)

_LOGGER = logging.getLogger(__name__)


class PoolAutomationCoordinator(DataUpdateCoordinator):
    """Manage pool automation state, MQTT, dosing loop, and tank tracking."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )
        self.entry = entry
        self._subscriptions: list[Any] = []
        self._store = Store(hass, STORE_VERSION, f"{STORE_KEY}_{entry.entry_id}")

        # Live sensor state
        self.ph: float | None = None
        self.orp: float | None = None
        self.temperature: float | None = None
        self.free_chlorine: float | None = None
        self.experimental_fc: float | None = None
        self.priority: str = PRIORITY_OK
        self.dose_ph_ml: float | None = None
        self.dose_chlorine_ml: float | None = None
        self.automation_enabled: bool = True

        # Tank remaining volumes — loaded from storage in async_setup
        self.hcl_remaining_ml: float | None = None
        self.naclo_remaining_ml: float | None = None

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
        """Subscribe to MQTT, register dosing loop, and set up tank tracking."""
        await self._load_tank_state()

        subscribe = mqtt.async_subscribe
        self._subscriptions.append(
            await subscribe(self.hass, self._topic(TOPIC_ORP_PH), self._handle_orp_ph)
        )
        self._subscriptions.append(
            await subscribe(self.hass, self._topic(TOPIC_ADD_PH), self._handle_add_ph)
        )
        self._subscriptions.append(
            await subscribe(self.hass, self._topic(TOPIC_ADD_CHLORINE), self._handle_add_chlorine)
        )
        self._subscriptions.append(
            await subscribe(
                self.hass,
                self._topic(TOPIC_RECOMMENDED_PRIORITY),
                self._handle_recommended_priority,
            )
        )

        # Hourly dosing cycle (replaces pool_auto_dose_* YAML automations)
        self._subscriptions.append(
            async_track_time_interval(
                self.hass,
                self.async_run_dosing_cycle,
                timedelta(seconds=DOSING_INTERVAL_SECONDS),
            )
        )

        # Tank tracking — listen for pump on→off transitions
        pump_ph = self.cfg.get(CONF_BINARY_PUMP_PH)
        if pump_ph:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass, [pump_ph], self._handle_ph_pump_state
                )
            )

        pump_cl = self.cfg.get(CONF_BINARY_PUMP_CHLORINE)
        if pump_cl:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass, [pump_cl], self._handle_chlorine_pump_state
                )
            )

        _LOGGER.info(
            "Pool Automation v3: MQTT + dosing loop (%ds) + tank tracking active",
            DOSING_INTERVAL_SECONDS,
        )

    async def async_unload(self) -> None:
        """Unsubscribe from MQTT and cancel all trackers."""
        for unsub in self._subscriptions:
            unsub()
        self._subscriptions.clear()

    # ------------------------------------------------------------------
    # Tank state persistence
    # ------------------------------------------------------------------
    async def _load_tank_state(self) -> None:
        """Load tank remaining volumes from storage. Treats a changed initial
        volume in config options as a tank refill."""
        stored = await self._store.async_load() or {}
        hcl_initial = self.cfg.get(CONF_TANK_HCL_INITIAL, DEFAULT_TANK_HCL_INITIAL)
        naclo_initial = self.cfg.get(CONF_TANK_NACLO_INITIAL, DEFAULT_TANK_NACLO_INITIAL)

        # If the configured initial volume changed since last save, treat as refill
        if stored.get("hcl_initial") != hcl_initial:
            self.hcl_remaining_ml = hcl_initial
        else:
            self.hcl_remaining_ml = stored.get("hcl_remaining_ml", hcl_initial)

        if stored.get("naclo_initial") != naclo_initial:
            self.naclo_remaining_ml = naclo_initial
        else:
            self.naclo_remaining_ml = stored.get("naclo_remaining_ml", naclo_initial)

    async def _save_tank_state(self) -> None:
        await self._store.async_save(
            {
                "hcl_remaining_ml": self.hcl_remaining_ml,
                "naclo_remaining_ml": self.naclo_remaining_ml,
                "hcl_initial": self.cfg.get(CONF_TANK_HCL_INITIAL, DEFAULT_TANK_HCL_INITIAL),
                "naclo_initial": self.cfg.get(CONF_TANK_NACLO_INITIAL, DEFAULT_TANK_NACLO_INITIAL),
            }
        )

    def reset_hcl_tank(self) -> None:
        """Reset HCl remaining to the initial configured volume (called from button)."""
        self.hcl_remaining_ml = self.cfg.get(CONF_TANK_HCL_INITIAL, DEFAULT_TANK_HCL_INITIAL)
        self.hass.async_create_task(self._save_tank_state())
        self.async_set_updated_data(self._build_data())
        _LOGGER.info("HCl tank reset to %.0f mL", self.hcl_remaining_ml)

    def reset_naclo_tank(self) -> None:
        """Reset NaClO remaining to the initial configured volume (called from button)."""
        self.naclo_remaining_ml = self.cfg.get(CONF_TANK_NACLO_INITIAL, DEFAULT_TANK_NACLO_INITIAL)
        self.hass.async_create_task(self._save_tank_state())
        self.async_set_updated_data(self._build_data())
        _LOGGER.info("NaClO tank reset to %.0f mL", self.naclo_remaining_ml)

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
    # Tank tracking – pump binary sensor state change handlers
    # ------------------------------------------------------------------
    @callback
    def _handle_ph_pump_state(self, event: Event) -> None:
        """Subtract actual dosed volume from HCl tank when pH pump finishes."""
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if not (old and new and old.state == "on" and new.state == "off"):
            return
        dosed_entity = self.cfg.get(CONF_SENSOR_DOSED_PH)
        if not dosed_entity or self.hcl_remaining_ml is None:
            return
        state = self.hass.states.get(dosed_entity)
        try:
            dosed = float(state.state)
            self.hcl_remaining_ml = max(0.0, self.hcl_remaining_ml - dosed)
            self.async_set_updated_data(self._build_data())
            self.hass.async_create_task(self._save_tank_state())
            _LOGGER.info("HCl: dosed %.1f mL → %.0f mL remaining", dosed, self.hcl_remaining_ml)
        except (ValueError, AttributeError):
            _LOGGER.warning("Could not read dosed pH volume from %s", dosed_entity)

    @callback
    def _handle_chlorine_pump_state(self, event: Event) -> None:
        """Subtract actual dosed volume from NaClO tank when chlorine pump finishes."""
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if not (old and new and old.state == "on" and new.state == "off"):
            return
        dosed_entity = self.cfg.get(CONF_SENSOR_DOSED_CHLORINE)
        if not dosed_entity or self.naclo_remaining_ml is None:
            return
        state = self.hass.states.get(dosed_entity)
        try:
            dosed = float(state.state)
            self.naclo_remaining_ml = max(0.0, self.naclo_remaining_ml - dosed)
            self.async_set_updated_data(self._build_data())
            self.hass.async_create_task(self._save_tank_state())
            _LOGGER.info("NaClO: dosed %.1f mL → %.0f mL remaining", dosed, self.naclo_remaining_ml)
        except (ValueError, AttributeError):
            _LOGGER.warning("Could not read dosed chlorine volume from %s", dosed_entity)

    # ------------------------------------------------------------------
    # Safety check
    # ------------------------------------------------------------------
    def _safe_to_dose(self, check_timer: bool = True) -> tuple[bool, str]:
        """Return (True, 'ok') if all safety conditions pass, else (False, reason).

        Args:
            check_timer: Set False for flocculant, which doesn't use the
                         chemicals timer and shouldn't be blocked by it.
        """
        if not self.automation_enabled:
            return False, "automation disabled"

        # Circulation must be above minimum RPM
        circ_entity = self.cfg.get(CONF_SENSOR_CIRCULATION)
        min_rpm = self.cfg.get(CONF_MIN_CIRCULATION, DEFAULT_MIN_CIRCULATION)
        if circ_entity:
            state = self.hass.states.get(circ_entity)
            try:
                rpm = float(state.state) if state else 0.0
            except (ValueError, AttributeError):
                rpm = 0.0
            if rpm < min_rpm:
                return False, f"circulation {rpm:.0f} RPM < minimum {min_rpm}"

        # Both dosing pumps must be idle before we trigger another dose
        for entity_id in (
            self.cfg.get(CONF_BINARY_PUMP_PH),
            self.cfg.get(CONF_BINARY_PUMP_CHLORINE),
        ):
            if entity_id:
                state = self.hass.states.get(entity_id)
                if state and state.state == "on":
                    return False, f"pump {entity_id} still running"

        # Chemicals timer prevents double-dosing within one cycle window
        if check_timer:
            timer_entity = self.cfg.get(CONF_TIMER_CHEMICALS)
            if timer_entity:
                state = self.hass.states.get(timer_entity)
                if state and state.state != "idle":
                    return False, "chemicals timer not idle"

        return True, "ok"

    # ------------------------------------------------------------------
    # Dosing cycle (replaces pool_auto_dose_* YAML automations)
    # ------------------------------------------------------------------
    async def async_run_dosing_cycle(self, now=None) -> None:
        """Automated hourly dosing cycle.

        Priority order:
          1. pH correction (HCl) — highest priority; skips chlorine/floc.
          2. Chlorine boost (NaClO) — only when pH is in range.
          3. Flocculant — only when priority is OK and pH is in range.

        Never doses two chemicals in the same cycle. Fires HA events so YAML
        automations can send push notifications without touching this logic.
        """
        safe, reason = self._safe_to_dose()
        if not safe:
            _LOGGER.debug("Dosing cycle skipped: %s", reason)
            self.hass.bus.async_fire(
                EVENT_DOSING_SKIPPED,
                {"reason": reason, "priority": self.priority},
            )
            return

        if self.priority == PRIORITY_PH_HIGH:
            ml = self.calculate_ph_dose_ml()
            if ml and ml > 0:
                await self.async_dose_ph()
                await self._start_chemicals_timer()
                self.hass.bus.async_fire(
                    EVENT_DOSING_STARTED,
                    {"type": "ph", "dose_ml": round(ml, 1), "ph": self.ph},
                )
                _LOGGER.info(
                    "Auto cycle: pH dose %.1f mL (pH=%.2f)", ml, self.ph or 0
                )

        elif self.priority == PRIORITY_CHLORINE_LOW:
            ml = self.calculate_chlorine_dose_ml()
            if ml and ml > 0:
                await self.async_dose_chlorine()
                await self._start_chemicals_timer()
                self.hass.bus.async_fire(
                    EVENT_DOSING_STARTED,
                    {
                        "type": "chlorine",
                        "dose_ml": round(ml, 1),
                        "fc": self.experimental_fc,
                    },
                )
                _LOGGER.info(
                    "Auto cycle: chlorine dose %.1f mL (FC=%.2f ppm)",
                    ml,
                    self.experimental_fc or 0,
                )

        elif (
            self.priority == PRIORITY_OK
            and self.cfg.get(CONF_ENABLE_FLOC, DEFAULT_ENABLE_FLOC)
        ):
            ph_min = self.cfg.get(CONF_PH_MIN, DEFAULT_PH_MIN)
            ph_max = self.cfg.get(CONF_PH_MAX, DEFAULT_PH_MAX)
            if self.ph is not None and ph_min <= self.ph <= ph_max:
                # Flocculant skips the chemicals timer check
                safe_floc, reason_floc = self._safe_to_dose(check_timer=False)
                if safe_floc:
                    await self.async_dose_floc()
                    self.hass.bus.async_fire(
                        EVENT_DOSING_STARTED, {"type": "floc"}
                    )
                    _LOGGER.info(
                        "Auto cycle: flocculant dose (pH=%.2f)", self.ph
                    )
                else:
                    _LOGGER.debug("Floc skipped: %s", reason_floc)

    async def _start_chemicals_timer(self) -> None:
        """Start the chemicals timer to block double-dosing within the same window."""
        timer_entity = self.cfg.get(CONF_TIMER_CHEMICALS)
        if timer_entity:
            await self.hass.services.async_call(
                "timer", "start", {"entity_id": timer_entity}, blocking=True
            )

    # ------------------------------------------------------------------
    # Chemistry calculations (pure Python, unit-testable)
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
        """Determine dosing priority from current pH and estimated FC."""
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
        elif self.experimental_fc < cl_min:
            self.priority = PRIORITY_CHLORINE_LOW
        elif self.experimental_fc > cl_max:
            self.priority = PRIORITY_CHLORINE_HIGH
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
        grams = (
            (pool_liters / 10000)
            * (CHLORINE_GRAMS_PER_10K_L_PER_PPM / strength_factor)
            * ppm_diff
        )
        return round(grams / CHLORINE_LIQUID_DENSITY, 2)

    # ------------------------------------------------------------------
    # Manual dose actions (also called by buttons and by dosing cycle)
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
                "button", "press", {"entity_id": button_entity}, blocking=True
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
                "button", "press", {"entity_id": button_entity}, blocking=True
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
                "number", "set_value", {"entity_id": num_vol, "value": vol}, blocking=True
            )
        if num_dur:
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": num_dur, "value": dur}, blocking=True
            )
        if btn:
            await self.hass.services.async_call(
                "button", "press", {"entity_id": btn}, blocking=True
            )
        _LOGGER.info("Flocculant dose triggered: %.1f mL for %ds", vol, dur)

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
            "hcl_remaining_ml": self.hcl_remaining_ml,
            "naclo_remaining_ml": self.naclo_remaining_ml,
        }

    async def _async_update_data(self) -> dict:
        """Periodic update – refresh sensor readings from HA state machine."""
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
