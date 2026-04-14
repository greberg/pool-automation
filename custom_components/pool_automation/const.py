"""Constants for Pool Automation integration."""

DOMAIN = "pool_automation"

# Configuration keys
CONF_POOL_VOLUME = "pool_volume_m3"
CONF_PH_MIN = "ph_min"
CONF_PH_MAX = "ph_max"
CONF_PH_TARGET = "ph_target"
CONF_CHLORINE_MIN = "chlorine_min"
CONF_CHLORINE_MAX = "chlorine_max"
CONF_CHLORINE_TARGET = "chlorine_target"
CONF_HCL_CONCENTRATION = "hcl_concentration"
CONF_NACLO_CONCENTRATION = "naclo_concentration"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_SENSOR_PH = "sensor_ph"
CONF_SENSOR_ORP = "sensor_orp"
CONF_SENSOR_TEMP = "sensor_temperature"
CONF_SENSOR_CIRCULATION = "sensor_circulation_rpm"
CONF_BUTTON_DOSE_PH = "button_dose_ph_down"
CONF_BUTTON_DOSE_CHLORINE = "button_dose_chlorine"
CONF_BUTTON_DOSE_FLOC = "button_dose_floc"
CONF_NUMBER_VOLUME_PH = "number_volume_ph"
CONF_NUMBER_VOLUME_CHLORINE = "number_volume_chlorine"
CONF_NUMBER_VOLUME_FLOC = "number_volume_floc"
CONF_NUMBER_DURATION_FLOC = "number_duration_floc"
CONF_TIMER_CHEMICALS = "timer_chemicals"
CONF_ENABLE_FLOC = "enable_floc"
CONF_FLOC_VOLUME = "floc_volume_ml"
CONF_FLOC_DURATION = "floc_duration_s"
CONF_MIN_CIRCULATION = "min_circulation_rpm"

# Defaults
DEFAULT_NAME = "Pool"
DEFAULT_POOL_VOLUME = 50.0
DEFAULT_PH_MIN = 7.2
DEFAULT_PH_MAX = 7.6
DEFAULT_PH_TARGET = 7.4
DEFAULT_CHLORINE_MIN = 1.0
DEFAULT_CHLORINE_MAX = 3.0
DEFAULT_CHLORINE_TARGET = 1.5
DEFAULT_HCL_CONCENTRATION = 15.0
DEFAULT_NACLO_CONCENTRATION = 12.5
DEFAULT_MQTT_TOPIC_PREFIX = "pool"
DEFAULT_ENABLE_FLOC = True
DEFAULT_FLOC_VOLUME = 10.0
DEFAULT_FLOC_DURATION = 55
DEFAULT_MIN_CIRCULATION = 1000

# MQTT topics (relative to prefix)
TOPIC_ORP_PH = "orpph"
TOPIC_FC = "fc"
TOPIC_EXPERIMENT_FC = "experiment_fc"
TOPIC_PRIORITY = "priority"
TOPIC_RECOMMENDED_PRIORITY = "recommendedpriority"
TOPIC_CALC_PH = "calculateamountph"
TOPIC_ADD_PH = "addamountph"
TOPIC_CALC_CHLORINE = "calculateamountchlorine"
TOPIC_ADD_CHLORINE = "addamountchlorine"

# Priority states
PRIORITY_OK = "OK"
PRIORITY_PH_HIGH = "ph"
PRIORITY_PH_LOW = "ph_minus"
PRIORITY_CHLORINE_LOW = "chlorine"
PRIORITY_CHLORINE_HIGH = "chlorine_high"

# FC estimation constants
FC_SLOPE = 83.7
FC_ORP_BASE = 770.0
FC_PH_FACTOR = 25.0
FC_PH_REFERENCE = 7.0

# Chlorine dosing: grams per 10,000 L per ppm at 100% strength
CHLORINE_GRAMS_PER_10K_L_PER_PPM = 13.0
CHLORINE_LIQUID_DENSITY = 1.2  # g/mL

# Scan interval
SCAN_INTERVAL_SECONDS = 60

# Coordinator update interval
COORDINATOR_UPDATE_INTERVAL = 60  # seconds

# Entity unique ID suffixes
ENTITY_FREE_CHLORINE = "free_chlorine"
ENTITY_EXPERIMENT_FC = "experimental_free_chlorine"
ENTITY_PRIORITY = "priority"
ENTITY_DOSE_PH = "dose_ph_ml"
ENTITY_DOSE_CHLORINE = "dose_chlorine_ml"
ENTITY_AUTOMATION_ENABLED = "automation_enabled"
ENTITY_MANUAL_DOSE_PH = "manual_dose_ph"
ENTITY_MANUAL_DOSE_CHLORINE = "manual_dose_chlorine"
