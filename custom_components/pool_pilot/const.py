"""Constants for Pool Pilot."""
from __future__ import annotations
from typing import Final

DOMAIN: Final = "pool_pilot"
VERSION: Final = "0.4.0"

CONF_POOL_NAME: Final = "pool_name"
CONF_VOLUME_M3: Final = "volume_m3"
CONF_POOL_TYPE: Final = "pool_type"
CONF_SURFACE_TYPE: Final = "surface_type"

CONF_TEMP_ENTITY: Final = "temp_entity"
CONF_PH_ENTITY: Final = "ph_entity"
CONF_ORP_ENTITY: Final = "orp_entity"
CONF_FC_ENTITY: Final = "fc_entity"
CONF_TA_ENTITY: Final = "ta_entity"
CONF_CH_ENTITY: Final = "ch_entity"
CONF_CYA_ENTITY: Final = "cya_entity"
CONF_SALT_ENTITY: Final = "salt_entity"
CONF_PUMP_SWITCH: Final = "pump_switch"
CONF_HEATPUMP_ENTITY: Final = "heatpump_entity"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_FORECAST_TEMP_ENTITY: Final = "forecast_temp_entity"
CONF_COVER_ENTITY: Final = "cover_entity"

CONF_TARGET_PH: Final = "target_ph"
CONF_TARGET_FC: Final = "target_fc"
CONF_FILTERING_MODE: Final = "filtering_mode"
CONF_FILTER_COEF: Final = "filter_coef"
CONF_MIN_FILTER_HOURS: Final = "min_filter_hours"
CONF_MAX_FILTER_HOURS: Final = "max_filter_hours"
CONF_HEAT_PUMP_PRIORITY: Final = "heat_pump_priority"
CONF_FREE_CHLORINE_MODE: Final = "free_chlorine_mode"

POOL_TYPE_CHLORINE = "chlorine"
POOL_TYPE_SALT = "saltwater"
POOL_TYPE_BROMINE = "bromine"
POOL_TYPES = [POOL_TYPE_CHLORINE, POOL_TYPE_SALT, POOL_TYPE_BROMINE]
SURFACE_TYPES = ["liner", "polyester", "concrete", "tile", "painted", "other"]
FILTERING_MODES = ["off", "manual", "auto"]

DEFAULT_TARGET_PH = 7.4
DEFAULT_TARGET_FC = 2.0
DEFAULT_FILTER_COEF = 2.0
DEFAULT_MIN_FILTER_HOURS = 2.0
DEFAULT_MAX_FILTER_HOURS = 24.0
DEFAULT_FREE_CHLORINE_MODE = False

PLATFORMS = ["sensor", "number", "button", "select", "switch"]
