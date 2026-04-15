"""Config flow for Pool Automation integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
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
    DEFAULT_CHLORINE_MAX,
    DEFAULT_CHLORINE_MIN,
    DEFAULT_CHLORINE_TARGET,
    DEFAULT_ENABLE_FLOC,
    DEFAULT_FLOC_DURATION,
    DEFAULT_FLOC_VOLUME,
    DEFAULT_HCL_CONCENTRATION,
    DEFAULT_MIN_CIRCULATION,
    DEFAULT_NACLO_CONCENTRATION,
    DEFAULT_NAME,
    DEFAULT_PH_MAX,
    DEFAULT_PH_MIN,
    DEFAULT_PH_TARGET,
    DEFAULT_POOL_VOLUME,
    DEFAULT_TANK_HCL_INITIAL,
    DEFAULT_TANK_NACLO_INITIAL,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("name", default=DEFAULT_NAME): str,
        vol.Required(CONF_POOL_VOLUME, default=DEFAULT_POOL_VOLUME): vol.Coerce(float),
        vol.Required(CONF_PH_MIN, default=DEFAULT_PH_MIN): vol.Coerce(float),
        vol.Required(CONF_PH_MAX, default=DEFAULT_PH_MAX): vol.Coerce(float),
        vol.Required(CONF_PH_TARGET, default=DEFAULT_PH_TARGET): vol.Coerce(float),
        vol.Required(CONF_CHLORINE_MIN, default=DEFAULT_CHLORINE_MIN): vol.Coerce(float),
        vol.Required(CONF_CHLORINE_MAX, default=DEFAULT_CHLORINE_MAX): vol.Coerce(float),
        vol.Required(CONF_CHLORINE_TARGET, default=DEFAULT_CHLORINE_TARGET): vol.Coerce(float),
        vol.Required(CONF_HCL_CONCENTRATION, default=DEFAULT_HCL_CONCENTRATION): vol.Coerce(float),
        vol.Required(CONF_NACLO_CONCENTRATION, default=DEFAULT_NACLO_CONCENTRATION): vol.Coerce(float),
        vol.Required(CONF_MQTT_TOPIC_PREFIX, default="pool"): str,
        vol.Optional(CONF_SENSOR_PH, default="sensor.pool_kit_ezo_ph_level"): str,
        vol.Optional(CONF_SENSOR_ORP, default="sensor.pool_kit_ezo_orp_level"): str,
        vol.Optional(CONF_SENSOR_TEMP, default="sensor.pool_temperature"): str,
        vol.Optional(CONF_SENSOR_CIRCULATION, default="sensor.cirkulation_rpm"): str,
        # v3: pump binary sensors for safety checks and tank tracking
        vol.Optional(
            CONF_BINARY_PUMP_PH,
            default="binary_sensor.pool_kit_pump_state_ph_down",
        ): str,
        vol.Optional(
            CONF_BINARY_PUMP_CHLORINE,
            default="binary_sensor.pool_kit_pump_state_orp",
        ): str,
        # v3: sensors reporting actual volume dosed each cycle (for tank tracking)
        vol.Optional(
            CONF_SENSOR_DOSED_PH,
            default="sensor.pool_kit_current_volume_dosed_ph_down",
        ): str,
        vol.Optional(
            CONF_SENSOR_DOSED_CHLORINE,
            default="sensor.pool_kit_current_volume_dosed_orp",
        ): str,
        vol.Optional(CONF_BUTTON_DOSE_PH, default="button.pool_kit_dose_ph_down"): str,
        vol.Optional(CONF_BUTTON_DOSE_CHLORINE, default="button.pool_kit_dose_orp"): str,
        vol.Optional(CONF_BUTTON_DOSE_FLOC, default="button.pool_kit_dose_floc_time_duration"): str,
        vol.Optional(CONF_NUMBER_VOLUME_PH, default="number.pool_kit_volume"): str,
        vol.Optional(CONF_NUMBER_VOLUME_CHLORINE, default="number.pool_kit_volume"): str,
        vol.Optional(CONF_NUMBER_VOLUME_FLOC, default="number.pool_kit_volume_floc"): str,
        vol.Optional(CONF_NUMBER_DURATION_FLOC, default="number.pool_kit_duration_floc"): str,
        vol.Optional(CONF_TIMER_CHEMICALS, default="timer.chemicals_dosed"): str,
        vol.Required(CONF_ENABLE_FLOC, default=DEFAULT_ENABLE_FLOC): bool,
        vol.Optional(CONF_FLOC_VOLUME, default=DEFAULT_FLOC_VOLUME): vol.Coerce(float),
        vol.Optional(CONF_FLOC_DURATION, default=DEFAULT_FLOC_DURATION): vol.Coerce(int),
        vol.Optional(CONF_MIN_CIRCULATION, default=DEFAULT_MIN_CIRCULATION): vol.Coerce(int),
        # v3: initial tank volumes — change here to trigger a refill reset
        vol.Optional(
            CONF_TANK_HCL_INITIAL, default=DEFAULT_TANK_HCL_INITIAL
        ): vol.Coerce(float),
        vol.Optional(
            CONF_TANK_NACLO_INITIAL, default=DEFAULT_TANK_NACLO_INITIAL
        ): vol.Coerce(float),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_POOL_VOLUME, default=DEFAULT_POOL_VOLUME): vol.Coerce(float),
        vol.Required(CONF_PH_MIN, default=DEFAULT_PH_MIN): vol.Coerce(float),
        vol.Required(CONF_PH_MAX, default=DEFAULT_PH_MAX): vol.Coerce(float),
        vol.Required(CONF_PH_TARGET, default=DEFAULT_PH_TARGET): vol.Coerce(float),
        vol.Required(CONF_CHLORINE_MIN, default=DEFAULT_CHLORINE_MIN): vol.Coerce(float),
        vol.Required(CONF_CHLORINE_MAX, default=DEFAULT_CHLORINE_MAX): vol.Coerce(float),
        vol.Required(CONF_CHLORINE_TARGET, default=DEFAULT_CHLORINE_TARGET): vol.Coerce(float),
        vol.Required(CONF_HCL_CONCENTRATION, default=DEFAULT_HCL_CONCENTRATION): vol.Coerce(float),
        vol.Required(CONF_NACLO_CONCENTRATION, default=DEFAULT_NACLO_CONCENTRATION): vol.Coerce(float),
        vol.Required(CONF_ENABLE_FLOC, default=DEFAULT_ENABLE_FLOC): bool,
        vol.Optional(CONF_FLOC_VOLUME, default=DEFAULT_FLOC_VOLUME): vol.Coerce(float),
        vol.Optional(CONF_FLOC_DURATION, default=DEFAULT_FLOC_DURATION): vol.Coerce(int),
        vol.Optional(CONF_MIN_CIRCULATION, default=DEFAULT_MIN_CIRCULATION): vol.Coerce(int),
        # v3: update tank initial volumes here when you refill the tanks
        vol.Optional(
            CONF_TANK_HCL_INITIAL, default=DEFAULT_TANK_HCL_INITIAL
        ): vol.Coerce(float),
        vol.Optional(
            CONF_TANK_NACLO_INITIAL, default=DEFAULT_TANK_NACLO_INITIAL
        ): vol.Coerce(float),
    }
)


class PoolAutomationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pool Automation."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get("name", DEFAULT_NAME),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return PoolAutomationOptionsFlow(config_entry)


class PoolAutomationOptionsFlow(config_entries.OptionsFlow):
    """Handle Pool Automation options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        cfg = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_POOL_VOLUME, default=cfg.get(CONF_POOL_VOLUME, DEFAULT_POOL_VOLUME)): vol.Coerce(float),
                vol.Required(CONF_PH_MIN, default=cfg.get(CONF_PH_MIN, DEFAULT_PH_MIN)): vol.Coerce(float),
                vol.Required(CONF_PH_MAX, default=cfg.get(CONF_PH_MAX, DEFAULT_PH_MAX)): vol.Coerce(float),
                vol.Required(CONF_PH_TARGET, default=cfg.get(CONF_PH_TARGET, DEFAULT_PH_TARGET)): vol.Coerce(float),
                vol.Required(CONF_CHLORINE_MIN, default=cfg.get(CONF_CHLORINE_MIN, DEFAULT_CHLORINE_MIN)): vol.Coerce(float),
                vol.Required(CONF_CHLORINE_MAX, default=cfg.get(CONF_CHLORINE_MAX, DEFAULT_CHLORINE_MAX)): vol.Coerce(float),
                vol.Required(CONF_CHLORINE_TARGET, default=cfg.get(CONF_CHLORINE_TARGET, DEFAULT_CHLORINE_TARGET)): vol.Coerce(float),
                vol.Required(CONF_HCL_CONCENTRATION, default=cfg.get(CONF_HCL_CONCENTRATION, DEFAULT_HCL_CONCENTRATION)): vol.Coerce(float),
                vol.Required(CONF_NACLO_CONCENTRATION, default=cfg.get(CONF_NACLO_CONCENTRATION, DEFAULT_NACLO_CONCENTRATION)): vol.Coerce(float),
                vol.Required(CONF_ENABLE_FLOC, default=cfg.get(CONF_ENABLE_FLOC, DEFAULT_ENABLE_FLOC)): bool,
                vol.Optional(CONF_FLOC_VOLUME, default=cfg.get(CONF_FLOC_VOLUME, DEFAULT_FLOC_VOLUME)): vol.Coerce(float),
                vol.Optional(CONF_FLOC_DURATION, default=cfg.get(CONF_FLOC_DURATION, DEFAULT_FLOC_DURATION)): vol.Coerce(int),
                vol.Optional(CONF_MIN_CIRCULATION, default=cfg.get(CONF_MIN_CIRCULATION, DEFAULT_MIN_CIRCULATION)): vol.Coerce(int),
                # v3 tank volumes — change to reset remaining after a refill
                vol.Optional(
                    CONF_TANK_HCL_INITIAL,
                    default=cfg.get(CONF_TANK_HCL_INITIAL, DEFAULT_TANK_HCL_INITIAL),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_TANK_NACLO_INITIAL,
                    default=cfg.get(CONF_TANK_NACLO_INITIAL, DEFAULT_TANK_NACLO_INITIAL),
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
