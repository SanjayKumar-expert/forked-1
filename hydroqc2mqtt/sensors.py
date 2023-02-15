"""Sensor definition list."""
from typing import TypedDict

# TODO: python 3.11 => uncomment Required
# from typing_extensions import Required


# TODO: python 3.11 => uncomment Required
class SensorType(TypedDict, total=False):
    """Sensor entity settings dict format."""

    name: str
    data_source: str
    device_class: str | None
    expire_after: int
    force_update: bool
    entity_category: str | None
    # device_class: Required[str | None]
    # expire_after: Required[int]
    # force_update: Required[bool]
    icon: str | None
    state_class: str | None
    unit: str | None
    sub_mqtt_topic: str
    object_id: str
    rates: list[str]
    attributes: dict[str, str]


class BinarySensorType(TypedDict, total=False):
    """Binary sensor entity settings dict format."""

    name: str
    data_source: str
    device_class: str | None
    expire_after: int
    force_update: bool
    icon: str
    sub_mqtt_topic: str
    object_id: str
    rates: list[str]
    attributes: dict[str, str]


HOURLY_CONSUMPTION_HISTORY_SWITCH = {
    "name": "Sync hourly consumption history",
    "icon": "mdi:clipboard-text-clock",
    "entity_category": "config",
    "sub_mqtt_topic": "contract/state",
    "optimistic": False,
}

HOURLY_CONSUMPTION_HISTORY_DAYS = {
    "name": "Days to sync in hourly consumption history",
    "icon": "mdi:calendar-clock",
    "entity_category": "config",
    "sub_mqtt_topic": "contract/state",
    "min_value": 0,
    "max_value": 800,
    "mode": "auto",
    "unit": "days",
    "step": 1,
    "optimistic": True,
    "start_value": 731,
}

HOURLY_CONSUMPTION_CLEAR_BUTTON = {
    "name": "Clear hourly consumption history",
    "icon": "mdi:broom",
    "entity_category": "config",
    "sub_mqtt_topic": "contract/state",
}


HOURLY_CONSUMPTION_TOTAL_SENSOR: SensorType = {
    "name": "Total hourly consumption",
    "device_class": "energy",
    "expire_after": 0,
    "entity_category": "diagnostic",
    "force_update": False,
    "icon": "mdi:lightning-bolt",
    "state_class": "total_increasing",
    "unit": "kWh",
    "sub_mqtt_topic": "contract/state",
}

HOURLY_CONSUMPTION_HAUT_SENSOR: SensorType = {
    "name": "High price hourly consumption",
    "device_class": "energy",
    "expire_after": 0,
    "entity_category": "diagnostic",
    "force_update": False,
    "icon": "mdi:lightning-bolt",
    "state_class": "total_increasing",
    "unit": "kWh",
    "sub_mqtt_topic": "contract/state",
}

HOURLY_CONSUMPTION_REG_SENSOR: SensorType = {
    "name": "Reg price hourly consumption",
    "device_class": "energy",
    "expire_after": 0,
    "entity_category": "diagnostic",
    "force_update": False,
    "icon": "mdi:lightning-bolt",
    "state_class": "total_increasing",
    "unit": "kWh",
    "sub_mqtt_topic": "contract/state",
}


SENSORS: dict[
    str, SensorType
] = {  # pylint: disable=consider-using-namedtuple-or-dataclass
    # Account
    "balance": {
        "name": "Balance",
        "data_source": "account.balance",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "account/state",
        "rates": ["ALL"],
    },
    # Contract
    "outage": {
        "name": "Next or current outage",
        "data_source": "contract.next_outage.start_date",
        "state_class": "measurement",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:calendar-start",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
        "attributes": {
            "end_date": "contract.next_outage.end_date",
            "cause": "contract.next_outage.cause.name",
            "planned_duration": "contract.next_outage.planned_duration",
            "code": "contract.next_outage.code.name",
            "state": "contract.next_outage.status.name",
            "emergency_level": "contract.next_outage.emergency_level",
            "is_planned": "contract.next_outage.is_planned",
        },
    },
    "current_billing_period_current_day": {
        "name": "Current billing period current day",
        "data_source": "contract.cp_current_day",
        "device_class": None,
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:calendar-start",
        "state_class": "measurement",
        "unit": "days",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_duration": {
        "name": "Current billing period duration",
        "data_source": "contract.cp_duration",
        "device_class": None,
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:calendar-expand-horizontal",
        "state_class": "measurement",
        "unit": "days",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_total_to_date": {
        "name": "Current billing period total to date",
        "data_source": "contract.cp_current_bill",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_projected_bill": {
        "name": "Current billing period projected bill",
        "data_source": "contract.cp_projected_bill",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_daily_bill_mean": {
        "name": "Current billing period daily bill mean",
        "data_source": "contract.cp_daily_bill_mean",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_daily_consumption_mean": {
        "name": "Current billing period daily consumption mean",
        "data_source": "contract.cp_daily_consumption_mean",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_total_consumption": {
        "name": "Current billing period total consumption",
        "data_source": "contract.cp_total_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "state_class": "total_increasing",
        "unit": "kWh",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_projected_total_consumption": {
        "name": "Current billing period projected total consumption",
        "data_source": "contract.cp_projected_total_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_average_temperature": {
        "name": "Current billing period average temperature",
        "data_source": "contract.cp_average_temperature",
        "device_class": "temperature",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:thermometer",
        "state_class": "measurement",
        "unit": "°C",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_kwh_cost_mean": {
        "name": "Current billing period kwh cost mean",
        "data_source": "contract.cp_kwh_cost_mean",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD/kWh",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_rate": {
        "name": "Current billing period rate",
        "data_source": "contract.rate",
        "device_class": None,
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:playlist-check",
        "state_class": None,
        "unit": None,
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    "current_billing_period_rate_option": {
        "name": "Current billing period rate option",
        "data_source": "contract.rate_option",
        "device_class": None,
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:playlist-star",
        "state_class": None,
        "unit": None,
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    # FlexD and DT (identical for now...)
    "current_billing_period_higher_price_consumption": {
        "name": "Current billing period higher price consumption",
        "data_source": "contract.cp_higher_price_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "contract/state",
        "rates": ["DT", "DPC"],
    },
    "current_billing_period_lower_price_consumption": {
        "name": "Current billing period lower price consumption",
        "data_source": "contract.cp_lower_price_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt-outline",
        "unit": "kWh",
        "sub_mqtt_topic": "contract/state",
        "rates": ["DT", "DPC"],
    },
    "amount_saved_vs_base_rate": {
        "name": "Net saving/loss vs rate D",
        "data_source": "contract.amount_saved_vs_base_rate",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "contract/state",
        "rates": ["DT", "DPC"],
    },
    # FlexD
    "dpc_state": {
        "name": "Current DPC period detail",
        "data_source": "contract.peak_handler.current_state",
        "device_class": None,
        "expire_after": 0,
        "force_update": False,
        "icon": None,
        "unit": None,
        "sub_mqtt_topic": "dpc-peak/state",
        "rates": ["DPC"],
    },
    "dpc_next_peak_start": {
        "name": "Next peak start",
        "data_source": "contract.peak_handler.next_peak.start_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "dpc-peak/next/peak",
        "rates": ["DPC"],
    },
    "dpc_next_peak_end": {
        "name": "Next peak end",
        "data_source": "contract.peak_handler.next_peak.end_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "dpc-peak/next/peak",
        "rates": ["DPC"],
    },
    "dpc_next_pre_heat_start": {
        "name": "Next Pre-heat start",
        "data_source": "contract.peak_handler.next_peak.preheat.start_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "dpc-peak/state",
        "rates": ["DPC"],
    },
    "dpc_critical_hours_count": {
        "name": "Number of critical hours",
        "data_source": "contract.critical_called_hours",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-alert-outline",
        "sub_mqtt_topic": "dpc-peak/state",
        "rates": ["DPC"],
        "attributes": {
            "max": "contract.max_critical_called_hours",
        },
    },
    "dpc_winter_days_count": {
        "name": "Number of winter days",
        "data_source": "contract.winter_total_days_last_update",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:calendar-range-outline",
        "sub_mqtt_topic": "dpc-peak/state",
        "rates": ["DPC"],
        "attributes": {
            "max": "contract.winter_total_days",
        },
    },
    # Winter credits
    "wc_state": {
        "name": "Current WC period detail",
        "data_source": "contract.peak_handler.current_state",
        "device_class": None,
        "expire_after": 0,
        "force_update": False,
        "icon": None,
        "unit": None,
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_cumulated_credit": {
        "name": "Cumulated winter credit",
        "data_source": "contract.peak_handler.cumulated_credit",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_projected_cumulated_credit": {
        "name": "Projected cumulated winter credit",
        "data_source": "contract.peak_handler.projected_cumulated_credit",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_next_anchor_start": {
        "name": "Next anchor start",
        "data_source": "contract.peak_handler.next_peak.anchor.start_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/next/anchor",
        "rates": ["DCPC"],
        "attributes": {
            "critical": "contract.peak_handler.next_peak.is_critical",
        },
    },
    "wc_next_anchor_end": {
        "name": "Next anchor end",
        "data_source": "contract.peak_handler.next_peak.anchor.end_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "wintercredits/next/anchor",
        "rates": ["DCPC"],
        "attributes": {
            "critical": "contract.peak_handler.next_peak.is_critical",
        },
    },
    "wc_next_peak_start": {
        "name": "Next peak start",
        "data_source": "contract.peak_handler.next_peak.start_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/next/peak",
        "rates": ["DCPC"],
        "attributes": {
            "critical": "contract.peak_handler.next_peak.is_critical",
        },
    },
    "wc_next_peak_end": {
        "name": "Next peak end",
        "data_source": "contract.peak_handler.next_peak.end_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "wintercredits/next/peak",
        "rates": ["DCPC"],
        "attributes": {
            "critical": "contract.peak_handler.next_peak.is_critical",
        },
    },
    "wc_next_critical_peak_start": {
        "name": "Next critical peak start",
        "data_source": "contract.peak_handler.next_critical_peak.start_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/next/critical",
        "rates": ["DCPC"],
    },
    "wc_next_critical_peak_end": {
        "name": "Next critical peak end",
        "data_source": "contract.peak_handler.next_critical_peak.end_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "wintercredits/next/critical",
        "rates": ["DCPC"],
    },
    "wc_next_pre_heat_start": {
        "name": "Next Pre-heat start",
        "data_source": "contract.peak_handler.next_peak.preheat.start_date",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
        "attributes": {
            "critical": "contract.peak_handler.next_peak.is_critical",
        },
    },
    # Yesterday
    "wc_yesterday_morning_peak_credit": {
        "name": "Yesterday morning peak saved credit",
        "data_source": "contract.peak_handler.yesterday_morning_peak.credit",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_morning_peak_actual_consumption": {
        "name": "Yesterday morning peak actual consumption",
        "data_source": "contract.peak_handler.yesterday_morning_peak.actual_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_morning_peak_ref_consumption": {
        "name": "Yesterday morning peak reference consumption",
        "data_source": "contract.peak_handler.yesterday_morning_peak.ref_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_morning_peak_saved_consumption": {
        "name": "Yesterday morning peak saved consumption",
        "data_source": "contract.peak_handler.yesterday_morning_peak.saved_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_evening_peak_credit": {
        "name": "Yesterday evening peak saved credit",
        "data_source": "contract.peak_handler.yesterday_evening_peak.credit",
        "device_class": "monetary",
        "state_class": "total",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "unit": "CAD",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_evening_peak_actual_consumption": {
        "name": "Yesterday evening peak actual consumption",
        "data_source": "contract.peak_handler.yesterday_evening_peak.actual_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_evening_peak_ref_consumption": {
        "name": "Yesterday evening peak reference consumption",
        "data_source": "contract.peak_handler.yesterday_evening_peak.ref_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
    "wc_yesterday_evening_peak_saved_consumption": {
        "name": "Yesterday evening peak saved consumption",
        "data_source": "contract.peak_handler.yesterday_evening_peak.saved_consumption",
        "device_class": "energy",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:home-lightning-bolt",
        "unit": "kWh",
        "sub_mqtt_topic": "wintercredits/yesterday",
        "rates": ["DCPC"],
    },
}
BINARY_SENSORS: dict[
    str, BinarySensorType
] = {  # pylint: disable=consider-using-namedtuple-or-dataclass
    # HydroQuebec
    "hydroquebec_website_status": {
        "name": "HydroQuebec website status",
        "data_source": "self._hydro_is_up",
        "device_class": "connectivity",
        "expire_after": 0,
        "force_update": False,
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    # Contracts
    "current_period_epp_enabled": {
        "name": "Current period epp enabled",
        "data_source": "contract.cp_epp_enabled",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:code-equal",
        "sub_mqtt_topic": "contract/state",
        "rates": ["ALL"],
    },
    # Winter credits
    "wc_critical": {
        # == wc_next_peak_critical
        "name": "Critical",
        "data_source": "contract.peak_handler.next_peak.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_critical_peak_in_progress": {
        "name": "Critical peak in progress",
        "data_source": "contract.peak_handler.current_peak_is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_pre_heat": {
        "name": "Pre-heat In Progress",
        "data_source": "contract.peak_handler.preheat_in_progress",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_next_anchor_critical": {
        "name": "Next Anchor Period Critical",
        # Est-ce que la période d'ancrage à venir est lié à une pointe critique"
        "data_source": "contract.peak_handler.next_anchor.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_next_peak_critical": {
        # == wc_critical
        # Est-ce que la prochaine période de pointe est critique true/false
        "name": "Next Peak Period Critical",
        "data_source": "contract.peak_handler.next_peak.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_upcoming_critical_peak": {
        # True si au moins un peaks donnés par l'API d'hydroQuebec n'est pas encore terminé
        "name": "Upcoming Critical Peak",
        "data_source": "contract.peak_handler.is_any_critical_peak_coming",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_critical_morning_peak_today": {
        "name": "Critical Morning Peak Today",
        "data_source": "contract.peak_handler.today_morning_peak.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:message-flash",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_critical_evening_peak_today": {
        "name": "Critical Evening Peak Today",
        "data_source": "contract.peak_handler.today_evening_peak.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:message-flash",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_critical_morning_peak_tomorrow": {
        "name": "Critical Morning Peak tomorrow",
        "data_source": "contract.peak_handler.tomorrow_morning_peak.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:message-flash",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    "wc_critical_evening_peak_tomorrow": {
        "name": "Critical Evening Peak tomorrow",
        "data_source": "contract.peak_handler.tomorrow_evening_peak.is_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:message-flash",
        "sub_mqtt_topic": "wintercredits/state",
        "rates": ["DCPC"],
    },
    # DPC
    "dpc_pre_heat": {
        "name": "Pre-heat In Progress",
        "data_source": "contract.peak_handler.preheat_in_progress",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "dpc-peak/state",
        "rates": ["DPC"],
    },
    "dpc_peak_in_progress": {
        "name": "Critical peak in progress",
        "data_source": "contract.peak_handler.peak_in_progress",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "dpc-peak/state",
        "rates": ["DPC"],
    },
}
