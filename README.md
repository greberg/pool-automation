# Pool Automation – Home Assistant Custom Component

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate HACS](https://github.com/greberg/pool-automation/actions/workflows/validate.yml/badge.svg)](https://github.com/greberg/pool-automation/actions/workflows/validate.yml)

A Home Assistant custom component for fully automated pool chemical management — pH (HCl) and chlorine (NaClO) dosing — built for the **ESPHome Pool Lab Kit**. Replaces the stand-alone Python MQTT app and manual YAML automations with a clean, native HA integration.

---

## Features

| Feature | Details |
|---|---|
| **Built-in dosing loop** | Hourly cycle runs entirely in Python — no YAML automations needed for dosing |
| **Priority logic** | pH correction always runs before chlorine; flocculant only when chemistry is OK |
| **Single safety gate** | Checks automation switch, circulation RPM, pump idle state, and timer before every dose |
| **Free chlorine estimation** | Calibrated ORP + pH formula — no external ML service needed |
| **Dose calculation** | Calculates exact mL of HCl / NaClO based on pool volume and chemical concentrations |
| **Flocculant dosing** | Automatic flocculant dose when pH and chlorine are both in range |
| **Tank volume tracking** | Tracks remaining HCl and NaClO, persists across HA restarts |
| **Manual override buttons** | Dose pH, chlorine, or flocculant on-demand; reset tank levels after a refill |
| **Event-based notifications** | Fires `pool_automation_dosing_started` HA events — wire up any notification service in YAML |
| **Editable set-points** | Target pH, target FC, pool volume, chemical concentrations as HA number entities |
| **Automation on/off switch** | One switch to pause all automatic dosing |
| **MQTT integration** | Publishes and subscribes using the same topics as your existing ESPHome kit |
| **HACS compatible** | Install and update via HACS |

---

## Prerequisites

- Home Assistant 2023.1 or newer
- MQTT integration configured
- ESPHome Pool Lab Kit sensors already integrated into HA:
  - `sensor.pool_kit_ezo_ph_level`
  - `sensor.pool_kit_ezo_orp_level`
  - `sensor.pool_temperature`
  - `sensor.cirkulation_rpm`
  - `binary_sensor.pool_kit_pump_state_ph_down`
  - `binary_sensor.pool_kit_pump_state_orp`
  - `sensor.pool_kit_current_volume_dosed_ph_down`
  - `sensor.pool_kit_current_volume_dosed_orp`
  - `button.pool_kit_dose_ph_down`
  - `button.pool_kit_dose_orp`
  - `button.pool_kit_dose_floc_time_duration`
  - `number.pool_kit_volume`
  - `number.pool_kit_volume_floc`
  - `number.pool_kit_duration_floc`
  - `timer.chemicals_dosed`

---

## Installation via HACS

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/greberg/pool-automation` as category **Integration**
3. Find **Pool Automation** in the HACS list and click **Download**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** → search **Pool Automation**
6. Fill in the configuration form (pool volume, target values, entity IDs)

---

## Entities Created

### Sensors
| Entity | Description |
|---|---|
| `sensor.pool_free_chlorine_fc` | Estimated free chlorine (ppm) from ORP + pH |
| `sensor.pool_management_priority` | Current action: `OK`, `ph`, `ph_minus`, `chlorine`, `chlorine_high` |
| `sensor.pool_ph_dose` | Calculated HCl dose needed (mL) |
| `sensor.pool_chlorine_dose` | Calculated NaClO dose needed (mL) |
| `sensor.pool_hcl_tank_remaining` | Remaining HCl volume in tank (mL) |
| `sensor.pool_naclo_tank_remaining` | Remaining NaClO volume in tank (mL) |

### Switch
| Entity | Description |
|---|---|
| `switch.pool_automation_mode` | Enable / disable all automatic dosing |

### Buttons
| Entity | Description |
|---|---|
| `button.pool_dose_ph_down` | Trigger a pH-down dose now |
| `button.pool_dose_chlorine` | Trigger a chlorine dose now |
| `button.pool_dose_flocculant` | Trigger a flocculant dose now |
| `button.pool_reset_hcl_tank` | Reset HCl remaining to configured initial volume |
| `button.pool_reset_naclo_tank` | Reset NaClO remaining to configured initial volume |

### Numbers (set-points, editable in UI)
| Entity | Description |
|---|---|
| `number.pool_target_ph` | Target pH (default 7.4) |
| `number.pool_target_free_chlorine` | Target FC in ppm (default 1.5) |
| `number.pool_volume` | Pool volume in m³ |
| `number.pool_hcl_concentration` | HCl acid concentration % |
| `number.pool_naclo_concentration` | NaClO liquid chlorine concentration % |

---

## How the Dosing Loop Works

The component runs its own hourly dosing cycle — no YAML automations are needed for scheduling or safety checks.

**Each hour, the coordinator:**
1. Checks all safety conditions (`_safe_to_dose`): automation switch on, circulation RPM above minimum, both dosing pumps idle, chemicals timer idle.
2. If conditions pass, doses based on priority:
   - **pH high** → dose HCl, start timer
   - **Chlorine low** → dose NaClO, start timer
   - **OK + flocculant enabled + pH in range** → dose flocculant
   - Never doses two chemicals in the same cycle.
3. Fires a `pool_automation_dosing_started` HA event with `type`, `dose_ml`, and current reading (`ph` or `fc`).

A `pool_automation_dosing_skipped` event is fired (with reason) whenever the safety check blocks a cycle — useful for debugging dashboards.

---

## Automations (YAML)

Copy `automations.yaml` into your HA automations. The dosing loop itself is now handled by the component, so this file only contains:

- **Push notifications** — listen to `pool_automation_dosing_started` events and forward to your phone
- **Out-of-range alerts** — ORP and pH threshold notifications
- **Season open/close** — scene activation + automation switch
- **Google Sheets logging** — every 30 minutes
- **FC model training** — MQTT publish on new lab measurement

---

## Tank Volume Tracking

The component tracks remaining HCl and NaClO volumes automatically:

- On each pump `on → off` transition, the actual dosed volume (read from `sensor.pool_kit_current_volume_dosed_*`) is subtracted from the tank remaining.
- Remaining volumes are **persisted to disk** and survive HA restarts.
- **To log a refill:** press `button.pool_reset_hcl_tank` or `button.pool_reset_naclo_tank`, or update the initial tank volume in the options flow — a changed initial value triggers a reset to that new volume.

---

## Configuration Options

All set-points are editable after setup via **Settings → Devices & Services → Pool Automation → Configure**.

| Option | Default | Description |
|---|---|---|
| Pool volume | 50 m³ | Used for dose calculations |
| pH min / max | 7.2 / 7.6 | Alert and dosing thresholds |
| pH target | 7.4 | Dose target |
| Chlorine min / max | 1.0 / 3.0 ppm | Alert thresholds |
| Chlorine target | 1.5 ppm | Dose target |
| HCl concentration | 15 % | Your acid bottle strength |
| NaClO concentration | 12.5 % | Your chlorine bottle strength |
| Enable flocculant | true | Auto flocculant dosing |
| Flocculant volume | 10 mL | Per dose |
| Flocculant duration | 55 s | Pump run time |
| Min circulation RPM | 1000 | Safety: only dose when pump running |
| HCl tank initial volume | 5000 mL | Starting volume — change to reset remaining after a refill |
| NaClO tank initial volume | 5000 mL | Starting volume — change to reset remaining after a refill |

---

## Migrating from the Python App

If you were running `pool_api.py` in Docker:

1. **Stop the Docker container** — the component handles all MQTT logic natively.
2. The component subscribes to the same `pool/orpph`, `pool/addamountph`, `pool/addamountchlorine` topics.
3. The FC estimation is built into the coordinator using the same calibrated formula.
4. The linear regression re-training (`chlorine_model/train`) is still handled via MQTT — keep the Python app running for that alone, or remove it if you don't use lab-calibrated FC updates.

---

## Credits

Built for a Höllviken pool running an Atlas Scientific EZO pH/ORP kit flashed with ESPHome. Calibration constants courtesy of real pool water measurements.
