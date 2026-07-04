"""Constants for Pool Pilot."""
from __future__ import annotations
from typing import Final

DOMAIN: Final = "pool_pilot"
VERSION: Final = "0.8.27"

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
FILTERING_MODES = ["manual", "auto_intelligent"]

DEFAULT_TARGET_PH = 7.4
DEFAULT_TARGET_FC = 2.0
DEFAULT_FILTER_COEF = 2.0
DEFAULT_MIN_FILTER_HOURS = 2.0
DEFAULT_MAX_FILTER_HOURS = 24.0
DEFAULT_FREE_CHLORINE_MODE = "measured"
CHLORINE_MODES = ["measured", "estimated"]

PLATFORMS = ["sensor", "number", "button", "select", "switch"]

# Auto intelligent filtration defaults
CONF_AUTO_START_TIME: Final = "auto_start_time"
CONF_AUTO_END_TIME: Final = "auto_end_time"
DEFAULT_AUTO_START_TIME: Final = "07:00"
DEFAULT_AUTO_END_TIME: Final = "22:00"

CONF_WATER_TEMP_ALERT_MIN: Final = "water_temp_alert_min"
CONF_WATER_TEMP_ALERT_MAX: Final = "water_temp_alert_max"
DEFAULT_WATER_TEMP_ALERT_MIN: Final = 6.0
DEFAULT_WATER_TEMP_ALERT_MAX: Final = 31.0

CONF_ALGAE_RISK_SENSITIVITY: Final = "algae_risk_sensitivity"
DEFAULT_ALGAE_RISK_SENSITIVITY: Final = 60.0


# Centered smart filtration
CONF_FILTRATION_CENTER_HOUR: Final = "filtration_center_hour"
DEFAULT_FILTRATION_CENTER_HOUR: Final = 12.0

DEFAULT_VOLUME_M3: Final = 50.0

# Notifications
CONF_NOTIFICATIONS_ENABLED: Final = "notifications_enabled"
CONF_NOTIFY_PERSISTENT: Final = "notify_persistent"
CONF_NOTIFY_MOBILE_SERVICES: Final = "notify_mobile_services"
CONF_NOTIFY_DAILY_SUMMARY_ENABLED: Final = "notify_daily_summary_enabled"
CONF_NOTIFY_DAILY_SUMMARY_TIME: Final = "notify_daily_summary_time"
CONF_NOTIFY_STOCK_LOW_ENABLED: Final = "notify_stock_low_enabled"
CONF_NOTIFY_BATTERY_LOW_ENABLED: Final = "notify_battery_low_enabled"

DEFAULT_NOTIFICATIONS_ENABLED: Final = False
DEFAULT_NOTIFY_PERSISTENT: Final = True
DEFAULT_NOTIFY_DAILY_SUMMARY_ENABLED: Final = False
DEFAULT_NOTIFY_DAILY_SUMMARY_TIME: Final = "09:00"
DEFAULT_NOTIFY_STOCK_LOW_ENABLED: Final = True
DEFAULT_NOTIFY_BATTERY_LOW_ENABLED: Final = True

CONF_NOTIFY_ALERTS_ENABLED: Final = "notify_alerts_enabled"

CONF_NOTIFY_RECOMMENDATIONS_ENABLED: Final = "notify_recommendations_enabled"

CONF_NOTIFY_FILTRATION_ENABLED: Final = "notify_filtration_enabled"

CONF_NOTIFY_STRIP_TEST_ENABLED: Final = "notify_strip_test_enabled"

CONF_NOTIFY_STRIP_TEST_DAYS: Final = "notify_strip_test_days"

DEFAULT_NOTIFY_ALERTS_ENABLED: Final = True

DEFAULT_NOTIFY_RECOMMENDATIONS_ENABLED: Final = True

DEFAULT_NOTIFY_FILTRATION_ENABLED: Final = False

DEFAULT_NOTIFY_STRIP_TEST_ENABLED: Final = False

DEFAULT_NOTIFY_STRIP_TEST_DAYS: Final = 7
