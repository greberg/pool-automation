# Pool Automation – Home Assistant Custom Component

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate HACS](https://github.com/greberg/pool-automation/actions/workflows/validate.yml/badge.svg)](https://github.com/greberg/pool-automation/actions/workflows/validate.yml)

A Home Assistant custom component for fully automated pool chemical management — pH (HCl) and chlorine (NaClO) dosing — built for the **ESPHome Pool Lab Kit**. Replaces the stand-alone Python MQTT app and manual YAML automations with a clean, native HA integration.

---

## Features

| Feature | Details |
|---|---|
| **Free chlorine estimation** | Calibrated ORP+pH formula (no external ML service needed) |
| **Priority logic** | Automatically determines whether to dose pH or chlorine first |
| **Dose calculation** | Calculates exact mL of HCl / NaClO based on pool volume and concentrations |
| **Flocculant dosing** | Scheduled flocculant doses when pH is in range |
| **Manual override buttons** | Dose pH, chlorine, or flocculant on-demand from the HA UI |
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

### Switch
| Entity | Description |
|---|---|
| `switch.pool_automation_mode` | Enable / disable all automatic dosing |

### Buttons (manual override)
| Entity | Description |
|---|---|
| `button.pool_dose_ph_down` | Trigger a pH-down dose now |
| `button.pool_dose_chlorine` | Trigger a chlorine dose now |
| `button.pool_dose_flocculant` | Trigger a flocculant dose now |

### Numbers (set-points, editable in UI)
| Entity | Description |
|---|---|
| `number.pool_target_ph` | Target pH (default 7.4) |
| `number.pool_target_free_chlorine` | Target FC in ppm (default 1.5) |
| `number.pool_volume` | Pool volume in m³ |
| `number.pool_hcl_concentration` | HCl acid concentration % |
| `number.pool_naclo_concentration` | NaClO liquid chlorine concentration % |

---

## Automations

Copy the contents of `automations.yaml` from this repo into your HA automations. These replace the old `pool.yaml` automations and reference the component entities instead of MQTT topics.

Key automations included:
- Hourly pH dosing (when priority = `ph`, circulation running, timer idle)
- Hourly chlorine dosing (when priority = `chlorine`)
- Hourly flocculant dosing (when pH in range)
- Season open/close (activates/deactivates automation mode)
- Out-of-range notifications (Swedish 🇸🇪 — customise as needed)
- Google Sheets logging every 30 min
- FC model training on new lab measurements

---

## Migrating from the Python App

If you were running `pool_api.py` in Docker:

1. **Stop the Docker container** — the component handles all MQTT logic natively.
2. The component subscribes to the same `pool/orpph`, `pool/priority`, `pool/addamountph`, `pool/addamountchlorine` topics.
3. The ML-based FC estimation is now built into the coordinator using the same calibrated formula.
4. The linear regression re-training feature (`chlorine_model/train`) is still handled via the MQTT broker — the Python app can be kept running for that alone, or you can remove it if you don't use lab-calibrated FC updates.

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

---

## Credits

Built for a Höllviken pool running an Atlas Scientific EZO pH/ORP kit flashed with ESPHome. Calibration constants courtesy of real pool water measurements.
