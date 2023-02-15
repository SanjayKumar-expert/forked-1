"""Module defining HydroQC Contract."""
import datetime
import logging
from typing import TypedDict, cast

import asyncio_mqtt as mqtt
import hydroqc
import paho.mqtt.client as paho
from hydroqc.account import Account
from hydroqc.contract import ContractDCPC, ContractDPC, ContractDT
from hydroqc.contract.common import Contract
from hydroqc.customer import Customer
from hydroqc.peak.cpc.consts import DEFAULT_PRE_HEAT_DURATION
from hydroqc.webuser import WebUser
from mqtt_hass_base.device import MqttDevice
from mqtt_hass_base.entity import (
    BinarySensorSettingsType,
    MqttBinarysensor,
    MqttSensor,
    MqttSwitch,
    SensorSettingsType,
)
from pytz import timezone

from hydroqc2mqtt.__version__ import VERSION
from hydroqc2mqtt.error import Hydroqc2MqttError
from hydroqc2mqtt.hourly_consump_handler import HourlyConsumpHandler
from hydroqc2mqtt.sensors import BINARY_SENSORS, SENSORS, BinarySensorType, SensorType

TZ_EASTERN = timezone("US/Eastern")


# TODO: python 3.11 => uncomment NotRequired
# from typing_extensions import NotRequired


# TODO: python 3.11 => remove total and uncomment NotRequired
class HydroqcContractConfigType(TypedDict, total=False):
    """Binary sensor entity settings dict format."""

    username: str
    password: str
    name: str
    customer: str
    account: str
    contract: str
    preheat_duration_minutes: int
    log_level: str
    http_log_level: str
    sync_hourly_consumption_enabled: bool
    home_assistant_websocket_url: str
    home_assistant_token: str
    rate: str | None
    rate_option: str | None
    sensors: list[str]
    binary_sensors: list[str]
    verify_ssl: bool
    _hydro_is_up: bool
    # verify_ssl: NotRequired[bool]
    # log_level: NotRequired[str]
    # http_log_level: NotRequired[str]
    # sensors: NotRequired[list[str]]
    # binary_sensors: NotRequired[list[str]]


class HydroqcContractDevice(MqttDevice):  # pylint: disable=too-many-instance-attributes
    """HydroQC Contract class."""

    consumption_history_ent_switch: MqttSwitch
    _customer: Customer | None
    _account: Account | None
    _contract: Contract | None

    def __init__(
        self,
        name: str,
        logger: logging.Logger,
        config: HydroqcContractConfigType,
        mqtt_discovery_root_topic: str,
        mqtt_data_root_topic: str,
        mqtt_client: mqtt.Client,
    ):
        """Create a new MQTT Sensor Facebook object."""
        MqttDevice.__init__(
            self,
            name,
            logger,
            mqtt_discovery_root_topic,
            mqtt_data_root_topic,
            mqtt_client,
        )
        self._ws_query_id = 1
        self._config = config
        self._webuser = WebUser(
            config["username"],
            config["password"],
            config.get("verify_ssl", True),
            log_level=config.get("log_level", "INFO"),
            http_log_level=config.get("http_log_level", "WARNING"),
        )
        self.sw_version = VERSION
        self.manufacturer = "hydroqc"
        self._config_rate: str | None = self._config.get("rate")
        self._contract_rate: str | None = None
        self._config_rate_option: str | None = self._config.get("rate_option")
        self._contract_rate_option: str | None = None
        self._customer_id = str(self._config["customer"])
        self._customer = None
        self._account_id = str(config["account"])
        self._account = None
        self._contract_id = str(config["contract"])
        self._contract = None
        self._home_assistant_websocket_url = config.get("home_assistant_websocket_url")
        self._home_assistant_token = config.get("home_assistant_token")
        self._hydro_is_up = False
        try:
            self._preheat_duration = int(
                config.get("preheat_duration_minutes", DEFAULT_PRE_HEAT_DURATION)
            )
        except ValueError as exp:
            raise Hydroqc2MqttError(
                f"PREHEAT_DURATION_MINUTES value can not be convert "
                f"to an integer for contract {self._contract_id}"
            ) from exp

        # By default we load all sensors
        self._sensor_list = SENSORS
        if "sensors" in self._config:
            self._sensor_list = {}
            # If sensors key is in the config file, we load only the ones listed there
            # Check if sensor exists
            for sensor_key in self._config["sensors"]:
                if sensor_key not in SENSORS:
                    raise Hydroqc2MqttError(
                        f"E0001: Sensor {sensor_key} doesn't exist. Fix your config."
                    )
                self._sensor_list[sensor_key] = SENSORS[sensor_key]

        # By default we load all binary sensors
        self._binary_sensor_list = BINARY_SENSORS
        if "binary_sensors" in self._config:
            self._binary_sensor_list = {}
            # If binary_sensors key is in the config file, we load only the ones listed there
            # Check if sensor exists
            for sensor_key in self._config["binary_sensors"]:
                if sensor_key not in BINARY_SENSORS:
                    raise Hydroqc2MqttError(
                        f"E0002: Binary sensor {sensor_key} doesn't exist. Fix your config."
                    )
                self._binary_sensor_list[sensor_key] = BINARY_SENSORS[sensor_key]

        self.add_identifier(self._contract_id)
        self._base_name = name
        self.name = f"hydroqc_{self._base_name}"
        self._hch = HourlyConsumpHandler(
            self._name,
            bool(
                config.get("sync_hourly_consumption_enabled", False)
                and config.get("home_assistant_websocket_url", False)
                and config.get("home_assistant_token", False)
            ),
            str(config.get("home_assistant_websocket_url", "")),
            str(config.get("home_assistant_token", "")),
            logger,
            self,
        )

    @property
    def config_rate(self) -> str | None:
        """Get Contract rate from config."""
        return self._config_rate

    @property
    def config_rate_option(self) -> str | None:
        """Get Contract rate option from config."""
        if (
            self._config_rate_option is not None
            and self._config_rate_option.lower() == "none"
        ):
            return ""
        return self._config_rate_option

    @property
    def rate(self) -> str | None:
        """Get Contract rate from config or contract itself."""
        if self.config_rate is not None:
            return self.config_rate
        return self._contract_rate

    @property
    def rate_option(self) -> str | None:
        """Get Contract rate option from config or contract itself."""
        if self.config_rate_option is not None:
            return self.config_rate_option
        return self._contract_rate_option

    @property
    def consumption_types(self) -> list[str]:
        """Get conumption types based on a Contract."""
        consumption_types = ["total"]
        if self.rate in {"DT", "DPC"}:
            consumption_types.append("reg")
            consumption_types.append("haut")
        return consumption_types

    async def check_hq_portal_status(self) -> bool:
        """Check if the HydroQuebec website is up and store the data in an attribute."""
        return await self._webuser.check_hq_portal_status()

    async def add_entities(self) -> None:
        """Add Home Assistant entities."""
        # Get contract to know if rates if there are not set
        if self.rate is None or self.rate_option is None:
            await self.get_contract()

        for sensor_key in self._sensor_list:
            entity_settings = SENSORS[sensor_key].copy()
            sensor_name = entity_settings["name"].capitalize()

            if self.rate is None or self.rate_option is None:
                # Skip sensors is rate or rate_option is None
                continue
            if (
                "ALL" not in entity_settings["rates"]
                and self.rate + self.rate_option not in entity_settings["rates"]
            ):
                # Skip sensors that are not in the current rate
                continue

            if ".winter_credit." in entity_settings[
                "data_source"
            ] and self.rate_option not in ("CPC",):
                # This is a Winter Credit sensor and the contract doesn't have it enabled
                continue

            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del entity_settings["data_source"]
            del entity_settings["name"]
            del entity_settings["sub_mqtt_topic"]
            del entity_settings["rates"]
            if "attributes" in entity_settings:
                del entity_settings["attributes"]
            entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            setattr(
                self,
                sensor_key,
                cast(
                    MqttSensor,
                    self.add_entity(
                        "sensor",
                        sensor_name,
                        f"{self._contract_id}-{sensor_name}",
                        cast(SensorSettingsType, entity_settings),
                        sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                    ),
                ),
            )

        for sensor_key in self._binary_sensor_list:
            b_entity_settings = BINARY_SENSORS[sensor_key].copy()
            sensor_name = b_entity_settings["name"].capitalize()

            if self.rate is None or self.rate_option is None:
                # Skip sensors is rate or rate_option is None
                continue
            if (
                "ALL" not in b_entity_settings["rates"]
                and self.rate + self.rate_option not in b_entity_settings["rates"]
            ):
                # Skip sensors that are not in the current rate
                continue

            if ".winter_credit." in b_entity_settings[
                "data_source"
            ] and self.rate_option not in ("CPC",):
                # This is a Winter Credit sensor and the contract doesn't have it enabled
                continue

            sub_mqtt_topic = b_entity_settings["sub_mqtt_topic"].lower().strip("/")
            del b_entity_settings["data_source"]
            del b_entity_settings["name"]
            del b_entity_settings["sub_mqtt_topic"]
            del b_entity_settings["rates"]
            b_entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            setattr(
                self,
                sensor_key,
                cast(
                    MqttBinarysensor,
                    self.add_entity(
                        "binarysensor",
                        sensor_name,
                        f"{self._contract_id}-{sensor_name}",
                        cast(BinarySensorSettingsType, b_entity_settings),
                        sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                    ),
                ),
            )

        self._hch.add_entities()

        self.logger.info("added %s ...", self.name)

    async def _login(self) -> bool:
        """Login to HydroQC website."""
        self.logger.info("Login")
        try:
            return await self._webuser.login()
        except hydroqc.error.HydroQcHTTPError:
            self.logger.error("Can not login to HydroQuebec web site")
            return False
        return True

    async def init_session(self) -> bool:
        """Initialize session on HydroQC website."""
        if self._webuser.session_expired:
            return await self._login()

        try:
            await self._webuser.refresh_session()
            self.logger.info("Refreshing session")
        except hydroqc.error.HydroQcHTTPError:
            # Try to login if the refresh session didn't work
            self.logger.info("Refreshing session failed, try to login")
            return await self._login()
        return True

    def _get_object_attribute_value(
        self,
        datasource: list[str],
        sensor_list: dict[str, SensorType] | dict[str, BinarySensorType],
        sensor_key: str,
        sensor_type: str,
    ) -> str | None:
        """Get object path to get the value of the current entity.

        Example: datasource = "contract.peak_handler.value_state_evening_event_today"
                 datasource = ["contract", "winter_credit", "value_state_evening_event_today"]

        Here we try get the value of the attribut "value_state_evening_event_today"
        of the object "winter_credit" which is an attribute of the object "contract"
        """
        customer = self._customer
        account = self._account
        contract = self._contract
        if None in (customer, account, contract):
            raise Hydroqc2MqttError(
                "E0017: Contract data was never fetch, "
                "we need to get valid data at least one time before updating sensors."
            )

        today = datetime.date.today()
        data_obj = locals()[datasource[0]]
        value = None
        in_winter_credit_season = False

        if self.rate_option == "CPC":
            contract = cast(ContractDCPC, contract)
            in_winter_credit_season = (
                contract.peak_handler.winter_start_date.date()
                <= today
                <= contract.peak_handler.winter_end_date.date()
            )
        reason = None
        ele = ""
        for index, ele in enumerate(datasource[1:]):
            if not in_winter_credit_season and isinstance(
                data_obj, hydroqc.peak.cpc.handler.CPCPeakHandler
            ):
                reason = "wc_sensor_not_in_season"
                break
            if hasattr(data_obj, ele) is False:
                reason = "missing_data"
                break
            if getattr(data_obj, ele) is None:
                reason = "data_not_available"
                break

            data_obj = getattr(data_obj, ele)
            # If it's the last element of the datasource that means, it's the value
            if index + 1 == len(datasource[1:]):
                if sensor_type == "BINARY_SENSORS":
                    value = "ON" if data_obj else "OFF"
                elif isinstance(data_obj, datetime.datetime):
                    value = data_obj.isoformat()
                elif (
                    isinstance(data_obj, (int, float))
                    and "device_class" in sensor_list[sensor_key]
                    and sensor_list[sensor_key]["device_class"] == "monetary"
                ):
                    value = str(round(data_obj, 2))
                elif isinstance(data_obj, datetime.timedelta):
                    value = f"{data_obj.seconds / 60} minutes"
                else:
                    value = data_obj

        if value is None and sensor_type != "ATTRIBUTES":
            if reason == "wc_sensor_not_in_season":
                self.logger.info("Not in winter credit season, ignoring %s", sensor_key)
            elif reason == "data_not_available":
                self.logger.info(
                    "The value of %s in sensor %s is unkwown (the value is null) at this time",
                    ".".join(datasource),
                    sensor_key,
                )
            elif reason == "missing_data":
                self.logger.warning(
                    "%s - The object %s doesn't have the attribute `%s` . "
                    "Maybe your contract doesn't have this data ?",
                    sensor_key,
                    data_obj,
                    ele,
                )
            else:
                self.logger.warning("Can not find value for: %s", sensor_key)

        return value

    async def _update_sensors(
        self,
        sensor_list: dict[str, SensorType] | dict[str, BinarySensorType],
        sensor_type: str,
    ) -> None:
        """Fetch contract data and update contract attributes."""
        sensor_config: dict[str, SensorType] | dict[str, BinarySensorType]
        if sensor_type == "SENSORS":
            self.logger.debug("Updating sensors")
            sensor_config = SENSORS
        elif sensor_type == "BINARY_SENSORS":
            self.logger.debug("Updating binary sensors")
            sensor_config = BINARY_SENSORS
        else:
            raise Hydroqc2MqttError(f"E0003: Sensor type {sensor_type} not supported")

        for sensor_key in sensor_list:
            if not hasattr(self, sensor_key):
                # The sensor doesn't exist, (like WC sensor when it's not enabled)
                continue
            # Get current entity
            entity = getattr(self, sensor_key)
            # Get object path to get the value of the current entity
            datasource = sensor_config[sensor_key]["data_source"].split(".")
            # Get object path to get the value of the attributes of the current entity
            attr_dss = sensor_config[sensor_key].get("attributes", {})

            value = self._get_object_attribute_value(
                datasource,
                sensor_list,
                sensor_key,
                sensor_type,
            )

            attributes = {}
            for attr_key, attr_ds in attr_dss.items():
                datasource = attr_ds.split(".")
                attr_value = self._get_object_attribute_value(
                    datasource,
                    sensor_list,
                    sensor_key,
                    "ATTRIBUTE",
                )
                attributes[attr_key] = attr_value

            if value is None:
                await entity.send_not_available()
            else:
                await entity.send_state(value, attributes)
                await entity.send_available()

    async def update(self, hydro_is_up: bool) -> None:
        """Update Home Assistant entities."""
        self.logger.info("Starting sensors update procedure")
        self._hydro_is_up = hydro_is_up
        # TODO if any api calls failed, we should NOT crash and set sensors to not_available
        # Fetch latest data
        if self._hydro_is_up:
            self.logger.info("Trying to fetch data...")
            try:
                await self.get_contract()
                if self._contract is None:
                    # TODO FIX ME
                    return
                await self._contract.get_periods_info()
                await self._contract.refresh_outages()

                if self.rate == "D" and self.rate_option == "CPC":
                    contract_dcpc = cast(ContractDCPC, self._contract)
                    contract_dcpc.set_preheat_duration(self._preheat_duration)
                    await contract_dcpc.peak_handler.refresh_data()
                elif self.rate == "DPC":
                    contract_dpc = cast(ContractDPC, self._contract)
                    contract_dpc.set_preheat_duration(self._preheat_duration)
                    await contract_dpc.get_dpc_data()
                    await contract_dpc.peak_handler.refresh_data()
                elif self.rate == "DT":
                    contract_dt = cast(ContractDT, self._contract)
                    await contract_dt.get_annual_consumption()
                self.logger.info("Data fetched")
            except hydroqc.error.HydroQcError as exp:
                self.logger.error(
                    "Error fetching data. Data and sensors will not be updated - %s - %s",
                    self.name,
                    exp,
                )
                return
        else:
            self.logger.warning(
                "Hydro-Québec website seems don't, I will not trying to fetch data."
            )

        # history sensors
        if self._hch.enabled:
            await self._hch.update()

        try:
            await self._update_sensors(self._sensor_list, "SENSORS")
            await self._update_sensors(self._binary_sensor_list, "BINARY_SENSORS")
            self.logger.info("Contract %s updated", self.name)
        except Hydroqc2MqttError as exp:
            self.logger.warning(exp)

    async def close(self) -> None:
        """Close HydroQC web session."""
        await self._webuser.close_session()

    async def _command_callback(
        self,
        msg: paho.MQTTMessage,
    ) -> None:
        """Do something on topic event."""
        # Handle history sync switch turned on
        if msg.topic == self._hch.consumption_history_ent_switch.command_topic:
            if msg.payload == b"ON":
                if not self._hch.is_consumption_history_syncing:
                    await self._hch.start_history_task()

        if msg.topic == self._hch.consumption_clear_ent_button.command_topic:
            if msg.payload == b"PRESS":
                await self._hch.clear_history()

    async def get_contract(self) -> tuple[Customer, Account, Contract]:
        """Get contract object."""
        await self._webuser.get_info()
        await self._webuser.fetch_customers_info()
        self._customer = self._webuser.get_customer(self._customer_id)
        self._account = self._customer.get_account(self._account_id)
        self._contract = self._account.get_contract(self._contract_id)
        self._contract_rate = self._contract.rate
        if self.config_rate is not None and self._contract_rate != self.config_rate:
            msg = (
                f"E0015: Your RATE config settings is not right `{self._config_rate}` "
                f"but it's actually `{self._contract_rate}`. Please fix your config."
            )
            raise Hydroqc2MqttError(msg)
        self._contract_rate_option = self._contract.rate_option
        if (
            self.config_rate_option is not None
            and self._contract_rate_option != self.config_rate_option
        ):
            msg = (
                f"E0016: Your RATE_OPTION config settings is not right `{self.config_rate_option}` "
                f"but it's actually `{self._contract_rate_option}`. Please fix your config."
            )
            raise Hydroqc2MqttError(msg)
        return (self._customer, self._account, self._contract)
