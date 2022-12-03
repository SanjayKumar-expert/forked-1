"""Module defining HydroQC Contract."""
import asyncio
import datetime
import json
import logging
from typing import TypedDict, cast

import aiohttp
import asyncio_mqtt as mqtt
import hydroqc
import paho.mqtt.client as paho
from dateutil.relativedelta import relativedelta
from hydroqc.webuser import WebUser
from hydroqc.winter_credit.consts import DEFAULT_PRE_HEAT_DURATION
from mqtt_hass_base.device import MqttDevice
from mqtt_hass_base.entity import (
    BinarySensorSettingsType,
    MqttBinarysensor,
    MqttButton,
    MqttNumber,
    MqttSensor,
    MqttSwitch,
    SensorSettingsType,
    SwitchSettingsType,
)
from packaging import version
from pytz import timezone

from hydroqc2mqtt.__version__ import VERSION
from hydroqc2mqtt.error import Hydroqc2MqttError, Hydroqc2MqttWSError
from hydroqc2mqtt.sensors import (
    BINARY_SENSORS,
    HOURLY_CONSUMPTION_CLEAR_BUTTON,
    HOURLY_CONSUMPTION_HISTORY_DAYS,
    HOURLY_CONSUMPTION_HISTORY_SWITCH,
    HOURLY_CONSUMPTION_SENSOR,
    SENSORS,
    BinarySensorType,
    SensorType,
)

TZ_EASTERN = timezone("US/Eastern")


class HAEnergyStatType(TypedDict):
    """Home Assistant energy hourly stat dict format."""

    start: str
    state: float
    sum: float


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
    sync_hourly_consumption: bool
    preheat_duration_minutes: int
    hourly_consumption_sensor_name: str | None
    home_assistant_websocket_url: str
    home_assistant_token: str
    verify_ssl: bool
    log_level: str
    http_log_level: str
    sensors: list[str]
    binary_sensors: list[str]
    # verify_ssl: NotRequired[bool]
    # log_level: NotRequired[str]
    # http_log_level: NotRequired[str]
    # sensors: NotRequired[list[str]]
    # binary_sensors: NotRequired[list[str]]


class HydroqcContractDevice(MqttDevice):
    """HydroQC Contract class."""

    consumption_history_ent_switch: MqttSwitch

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
        self._customer_id = str(self._config["customer"])
        self._account_id = str(config["account"])
        self._contract_id = str(config["contract"])
        self._sync_hourly_consumption = config.get("sync_hourly_consumption", False)
        self.hourly_consumption_sensor_name = config.get(
            "hourly_consumption_sensor_name"
        )
        self._home_assistant_websocket_url = config.get("home_assistant_websocket_url")
        self._home_assistant_token = config.get("home_assistant_token")
        self._preheat_duration = config.get(
            "preheat_duration_minutes", DEFAULT_PRE_HEAT_DURATION
        )
        self._sync_hourly_consumption_history_task: asyncio.Task[None] | None = None
        self._got_first_hourly_consumption_data: bool = False

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

        connections = {
            "customer": self._customer_id,
            "account": self._account_id,
            "contract": self._contract_id,
        }
        self.add_connections(connections)
        self.add_identifier(str(config["contract"]))
        self._base_name = name
        self.name = f"hydroqc_{self._base_name}"

    @property
    def hourly_consumption_sync_enabled(self) -> bool:
        """Check if the hourly consumption sync feature is enabled."""
        if (
            self._sync_hourly_consumption
            and self._home_assistant_websocket_url
            and self._home_assistant_token
        ):
            return True
        return False

    @property
    def is_consumption_history_syncing(self) -> bool:
        """Is the history syncing task running."""
        if (
            self._sync_hourly_consumption_history_task is not None
            and not self._sync_hourly_consumption_history_task.done()
        ):
            return True
        return False

    async def add_entities(self) -> None:
        """Add Home Assistant entities."""
        # Get contract to know if WC is enabled
        await self._webuser.get_info()
        await self._webuser.fetch_customers_info()
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)

        for sensor_key in self._sensor_list:
            entity_settings = SENSORS[sensor_key].copy()
            sensor_name = entity_settings["name"].capitalize()

            if (
                ".winter_credit." in entity_settings["data_source"]
                and not contract.winter_credit.is_enabled
            ):
                # This is a Winter Credit sensor and the contract doesn't have it enabled
                continue

            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del entity_settings["data_source"]
            del entity_settings["name"]
            del entity_settings["sub_mqtt_topic"]
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

            if (
                ".winter_credit." in b_entity_settings["data_source"]
                and not contract.winter_credit.is_enabled
            ):
                # This is a Winter Credit sensor and the contract doesn't have it enabled
                continue

            sub_mqtt_topic = b_entity_settings["sub_mqtt_topic"].lower().strip("/")
            del b_entity_settings["data_source"]
            del b_entity_settings["name"]
            del b_entity_settings["sub_mqtt_topic"]
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

        if self.hourly_consumption_sync_enabled:
            # HOURLY_CONSUMPTION_SENSOR
            self.logger.info("Consumption sync enabled")
            entity_settings = HOURLY_CONSUMPTION_SENSOR.copy()
            sensor_name = entity_settings["name"].capitalize()
            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del entity_settings["name"]
            del entity_settings["sub_mqtt_topic"]
            entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            self.hourly_consumption_entity = cast(
                MqttSensor,
                self.add_entity(
                    "sensor",
                    sensor_name,
                    f"{self._contract_id}-{sensor_name}",
                    cast(SensorSettingsType, entity_settings),
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                ),
            )

            # History days
            number_entity_settings = HOURLY_CONSUMPTION_HISTORY_DAYS.copy()
            sensor_name = str(number_entity_settings["name"]).capitalize()
            sub_mqtt_topic = (
                str(number_entity_settings["sub_mqtt_topic"]).lower().strip("/")
            )
            del number_entity_settings["name"]
            del number_entity_settings["sub_mqtt_topic"]
            number_entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            self.consumption_history_ent_number = cast(
                MqttNumber,
                self.add_entity(
                    "number",
                    sensor_name,
                    f"{self._contract_id}-{sensor_name}",
                    cast(SwitchSettingsType, number_entity_settings),
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                    subscriptions={"command_topic": self._command_callback},
                ),
            )

            # History switch
            switch_entity_settings = HOURLY_CONSUMPTION_HISTORY_SWITCH.copy()
            sensor_name = str(switch_entity_settings["name"]).capitalize()
            sub_mqtt_topic = (
                str(switch_entity_settings["sub_mqtt_topic"]).lower().strip("/")
            )
            del switch_entity_settings["name"]
            del switch_entity_settings["sub_mqtt_topic"]
            switch_entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            self.consumption_history_ent_switch = cast(
                MqttSwitch,
                self.add_entity(
                    "switch",
                    sensor_name,
                    f"{self._contract_id}-{sensor_name}",
                    cast(SwitchSettingsType, switch_entity_settings),
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                    subscriptions={"command_topic": self._command_callback},
                ),
            )

            # Clear History button
            button_entity_settings = HOURLY_CONSUMPTION_CLEAR_BUTTON.copy()
            sensor_name = str(button_entity_settings["name"]).capitalize()
            sub_mqtt_topic = (
                str(button_entity_settings["sub_mqtt_topic"]).lower().strip("/")
            )
            del button_entity_settings["name"]
            del button_entity_settings["sub_mqtt_topic"]
            button_entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            self.consumption_clear_ent_button = cast(
                MqttButton,
                self.add_entity(
                    "button",
                    sensor_name,
                    f"{self._contract_id}-{sensor_name}",
                    cast(SwitchSettingsType, button_entity_settings),
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                    subscriptions={"command_topic": self._command_callback},
                ),
            )

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

    async def _update_sensors(
        self,
        sensor_list: dict[str, SensorType] | dict[str, BinarySensorType],
        sensor_type: str,
        customer: hydroqc.customer.Customer,  # pylint: disable=unused-argument
        account: hydroqc.account.Account,  # pylint: disable=unused-argument
        contract: hydroqc.contract.Contract,  # pylint: disable=unused-argument
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

        today = datetime.date.today()
        for sensor_key in sensor_list:
            if not hasattr(self, sensor_key):
                # The sensor doesn't exist, (like WC sensor when it's not enabled)
                continue
            # Get current entity
            entity = getattr(self, sensor_key)
            # Get object path to get the value of the current entity
            datasource = sensor_config[sensor_key]["data_source"].split(".")
            # Example: datasource = "contract.winter_credit.value_state_evening_event_today"
            # datasource = ["contract", "winter_credit", "value_state_evening_event_today"]
            # Here we try get the value of the attribut "value_state_evening_event_today"
            # of the object "winter_credit" which is an attribute of the object "contract"
            data_obj = locals()[datasource[0]]
            value = None
            in_winter_credit_season = False
            if contract.winter_credit.is_enabled:
                in_winter_credit_season = (
                    contract.winter_credit.winter_start_date.date()
                    <= today
                    <= contract.winter_credit.winter_end_date.date()
                )
            reason = None
            ele = ""
            for index, ele in enumerate(datasource[1:]):
                if not in_winter_credit_season and isinstance(
                    data_obj, hydroqc.winter_credit.handler.WinterCreditHandler
                ):
                    reason = "wc_sensor_not_in_season"
                    break
                if not hasattr(data_obj, ele):
                    reason = "missing_data"
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
                    else:
                        value = data_obj

            if value is None:
                if reason == "wc_sensor_not_in_season":
                    self.logger.info(
                        "Not in winter credit season, ignoring %s", sensor_key
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
                await entity.send_not_available()
            else:
                await entity.send_state(value, {})
                await entity.send_available()

    async def update(self) -> None:
        """Update Home Assistant entities."""
        self.logger.info("Updating ...")
        # TODO if any api calls failed, we should NOT crash and set sensors to not_available
        # Fetch latest data
        self.logger.info("Fetching data...")
        # if needed:
        await self._webuser.get_info()
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)
        contract.set_preheat_duration(self._preheat_duration)
        # fetch consumption and wintercredits
        # if needed:
        await contract.get_periods_info()
        if contract.winter_credit.is_enabled:
            await contract.winter_credit.refresh_data()
        self.logger.info("Data fetched")

        # history
        if self.hourly_consumption_sync_enabled:
            await self.consumption_history_ent_switch.send_available()
            if self.is_consumption_history_syncing:
                await self.consumption_history_ent_switch.send_on()
            else:
                await self.consumption_history_ent_switch.send_off()

            await self.consumption_clear_ent_button.send_available()
            await self.consumption_history_ent_number.send_available()

        await self._update_sensors(
            self._sensor_list, "SENSORS", customer, account, contract
        )
        await self._update_sensors(
            self._binary_sensor_list, "BINARY_SENSORS", customer, account, contract
        )
        self.logger.info("Updated %s ...", self.name)

    async def close(self) -> None:
        """Close HydroQC web session."""
        await self._webuser.close_session()

    @property
    def hourly_consumption_entity_id(self) -> str:
        """Get the entity_id of the Hourly consumption HA sensor."""
        entity_id = f"{self.name}_hourly_consumption"
        if self.hourly_consumption_sensor_name is not None:
            entity_id = self.hourly_consumption_sensor_name
        return f"sensor.{entity_id}".lower()

    async def sync_consumption_statistics(self) -> None:
        """Sync hourly consumption statistics.

        It synchronizes all the hourly data of yesterday and today.
        """
        if not self.hourly_consumption_sync_enabled:
            # Feature disabled
            return
        if self.is_consumption_history_syncing:
            # Historical stats currently syncing
            # So we do nothing
            return

        await self._webuser.get_info()
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)
        # We send data for today and yesterday to be sure to not miss and data
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        await self.get_historical_statistics(contract, yesterday)
        await self.hourly_consumption_entity.send_available()

    async def _command_callback(
        self,
        msg: paho.MQTTMessage,
    ) -> None:
        """Do something on topic event."""
        # Handle history sync switch turned on
        if msg.topic == self.consumption_history_ent_switch.command_topic:
            if msg.payload == b"ON":
                if not self.is_consumption_history_syncing:
                    await self.start_history_task()

        if msg.topic == self.consumption_clear_ent_button.command_topic:
            if msg.payload == b"PRESS":
                await self.clear_history()

    async def connect_hass_ws(
        self, client: aiohttp.ClientSession
    ) -> tuple[aiohttp.ClientWebSocketResponse, str]:
        """Connect and login to Home Assistant websocket API."""
        try:
            websocket = await client.ws_connect(str(self._home_assistant_websocket_url))
        except aiohttp.client_exceptions.ClientConnectorError as exp:
            raise Hydroqc2MqttWSError(
                f"E0005: Error Websocket connection error - {exp}"
            ) from exp

        response = await websocket.receive_json()
        if response.get("type") != "auth_required":
            str_response = json.dumps(response)
            raise Hydroqc2MqttWSError(f"E0006: Bad server response: ${str_response}")
        ha_version = response["ha_version"]

        # Auth
        await websocket.send_json(
            {"type": "auth", "access_token": self._home_assistant_token}
        )
        response = await websocket.receive_json()
        if response.get("type") != "auth_ok":
            raise Hydroqc2MqttWSError("E0007: Bad Home Assistant websocket token")
        return websocket, ha_version

    async def clear_history(self) -> None:
        """Clear all statistics of the hourly consumption entity."""
        self.logger.info("Cleaning hourly consumption history")
        if (
            self._sync_hourly_consumption_history_task is not None
            and not self._sync_hourly_consumption_history_task.done()
        ):
            self._sync_hourly_consumption_history_task.cancel()
            try:
                self.logger.info(
                    "Stopping (forced) hourly consumption history sync task"
                )
                await self._sync_hourly_consumption_history_task
            except asyncio.CancelledError:
                self.logger.info(
                    "Stopped (forced) hourly consumption history sync task"
                )
        self._ws_query_id = 1
        async with aiohttp.ClientSession() as client:
            websocket, _ = await self.connect_hass_ws(client)

            await websocket.send_json(
                {
                    "id": self._ws_query_id,
                    "statistic_ids": [self.hourly_consumption_entity_id],
                    "type": "recorder/clear_statistics",
                }
            )
            response = await websocket.receive_json()
            if response.get("success") is not True:
                reason = response.get("error", {}).get("message", "Unknown")
                raise Hydroqc2MqttWSError(
                    f"E0008: Error trying to clear consumption statistics - Reason: {reason}"
                )
        await self.consumption_clear_ent_button.send_available()
        self.logger.info("Cleaning hourly consumption history done")

    async def start_history_task(self) -> None:
        """Start a asyncio task to fetch all the hourly data stored by HydroQc."""
        self.logger.info("Starting hourly consumption history sync task")
        loop = asyncio.get_running_loop()
        self._sync_hourly_consumption_history_task = loop.create_task(
            self.get_hourly_consumption_history()
        )

    async def get_hourly_consumption_history(self) -> None:
        """Fetch all history of the hourly consumption."""
        await self.consumption_history_ent_switch.send_on()
        await self._webuser.get_info()
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)
        # Get two years ago plus few days
        today = datetime.date.today()
        if self.consumption_history_ent_number.current_value is None:
            days = 731
        else:
            days = int(self.consumption_history_ent_number.current_value)
        oldest_data_date = today - relativedelta(days=days)
        # Get contract start date
        await contract.get_info()
        if contract.start_date is not None:
            contract_start_date = datetime.date.fromisoformat(str(contract.start_date))
            # Get the youngest date between contract start date VS 2 years ago
            start_date = (
                oldest_data_date
                if contract_start_date < oldest_data_date
                else contract_start_date
            )
        else:
            start_date = oldest_data_date
        await self.get_historical_statistics(contract, start_date)
        await self.consumption_history_ent_switch.send_off()
        self.logger.info("Hourly consumption history sync done.")

    async def get_historical_statistics(
        self, contract: hydroqc.contract.Contract, data_date: datetime.date
    ) -> None:
        """Fetch hourly data from a specific day to today and send it to Home Assistant.

        It synchronizes all the hourly data of the data_date
        - from HydroQc (using hydroqc lib)
        - to Home assistant using websocket
        """
        today = datetime.date.today()
        # We have 5 tries to fetch all historical data
        retry = 5
        self._got_first_hourly_consumption_data = False
        while data_date <= today:
            try:
                raw_data = await contract.get_hourly_consumption(data_date.isoformat())
            except hydroqc.error.HydroQcHTTPError as exp:
                if not self._got_first_hourly_consumption_data:
                    self.logger.info(
                        "There is not data for on %s. "
                        "You can ignore the previous error message",
                        data_date.isoformat(),
                    )
                    data_date += datetime.timedelta(days=1)
                    continue
                if retry > 0:
                    self.logger.warning(
                        "Failed to sync all historical data on %s. Retrying %s/5 in 30 seconds",
                        data_date.isoformat(),
                        retry,
                    )
                    await asyncio.sleep(30)
                    self.logger.warning(
                        "Retrying to sync all historical data on %s (%s/5)",
                        data_date.isoformat(),
                        retry,
                    )
                    # await self.init_session()
                    await self._login()
                    # await self.
                    retry -= 1
                    continue

                self.logger.error(
                    "Error getting historical consumption data on %s. Stopping import",
                    data_date.isoformat(),
                )
                raise Hydroqc2MqttError(f"E0004: {exp}") from exp
            self._got_first_hourly_consumption_data = True
            stats: list[HAEnergyStatType] = []
            for data in raw_data["results"]["listeDonneesConsoEnergieHoraire"]:
                stat: HAEnergyStatType = {"start": "", "state": 0, "sum": 0}
                hour_splitted: list[int] = [int(e) for e in data["heure"].split(":", 2)]
                start_date = datetime.datetime.combine(
                    data_date,
                    datetime.time(hour_splitted[0], hour_splitted[1], hour_splitted[2]),
                )
                localized_start_date = TZ_EASTERN.localize(start_date)
                stat["start"] = localized_start_date.isoformat()
                # TODO handle consoHaut and consoReg
                stat["state"] = data["consoTotal"]
                self.logger.debug("%s - %s", stat["start"], data["consoTotal"])
                stats.append(stat)

            await self.send_consumption_statistics(stats, data_date)
            data_date += datetime.timedelta(days=1)
        self.logger.info("Success - hourly consumption sync task")

    async def send_consumption_statistics(
        self, stats: list[HAEnergyStatType], data_date: datetime.date
    ) -> None:
        """Send all hourly data of a whole day to Home Assistant.

        It uses websocket to send data to Home Assistant
        """
        # the consumption data are relative to the 00:00:00 of the give day
        if not self.hourly_consumption_sync_enabled:
            return
        self._ws_query_id = 1
        try:
            async with aiohttp.ClientSession() as client:
                websocket, ha_version = await self.connect_hass_ws(client)
                # Get data from yesterday
                data_start_date_str = TZ_EASTERN.localize(
                    datetime.datetime.combine(
                        data_date - datetime.timedelta(days=1), datetime.time(0, 0)
                    )
                ).isoformat()
                data_end_date_str = TZ_EASTERN.localize(
                    datetime.datetime.combine(data_date, datetime.time(0, 0))
                ).isoformat()

                websocket_call_type = (
                    "history/statistics_during_period"
                    if version.parse(ha_version) < version.parse("2022.10.0")
                    else "recorder/statistics_during_period"
                )
                await websocket.send_json(
                    {
                        "end_time": data_end_date_str,
                        "id": self._ws_query_id,
                        "period": "day",
                        "start_time": data_start_date_str,
                        "statistic_ids": [self.hourly_consumption_entity_id],
                        "type": websocket_call_type,
                    }
                )
                self._ws_query_id += 1
                response = await websocket.receive_json()
                if not response.get("result"):
                    base_sum = 0
                else:
                    # Get sum from response
                    base_sum = response["result"][self.hourly_consumption_entity_id][
                        -1
                    ]["sum"]
                # Add sum from last yesterday's data
                for index, stat in enumerate(stats):
                    if index == 0:
                        stat["sum"] = base_sum + stat["state"]
                    else:
                        stat["sum"] = stat["state"] + stats[index - 1]["sum"]

                # Send today's data
                await websocket.send_json(
                    {
                        "id": self._ws_query_id,
                        "type": "recorder/import_statistics",
                        "metadata": {
                            "has_mean": False,
                            "has_sum": True,
                            "name": None,
                            "source": "recorder",
                            "statistic_id": self.hourly_consumption_entity_id,
                            "unit_of_measurement": "kWh",
                        },
                        "stats": stats,
                    }
                )
                self._ws_query_id += 1
                response = await websocket.receive_json()
                if response.get("success") is not True:
                    reason = response.get("error", {}).get("message", "Unknown")
                    raise Hydroqc2MqttWSError(
                        f"E0008: Error trying to push consumption statistics - Reason: {reason}"
                    )
                self.logger.debug(
                    "Successfully import consumption statistics for %s",
                    {data_end_date_str},
                )

        except Exception as exp:
            raise Hydroqc2MqttWSError(f"E0009: {exp}") from exp
