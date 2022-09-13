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
from hydroqc.webuser import WebUser
from mqtt_hass_base.device import MqttDevice
from mqtt_hass_base.entity import (
    BinarySensorSettingsType,
    MqttBinarysensor,
    MqttSensor,
    MqttSwitch,
    SensorSettingsType,
    SwitchSettingsType,
)

from hydroqc2mqtt.__version__ import VERSION
from hydroqc2mqtt.error import Hydroqc2MqttError, Hydroqc2MqttWSError
from hydroqc2mqtt.sensors import (
    BINARY_SENSORS,
    HOURLY_CONSUMPTION_HISTORY_SWITCH,
    HOURLY_CONSUMPTION_SENSOR,
    SENSORS,
    BinarySensorType,
    SensorType,
)


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

    def add_entities(self) -> None:
        """Add Home Assistant entities."""
        for sensor_key in self._sensor_list:
            entity_settings = SENSORS[sensor_key].copy()
            sensor_name = entity_settings["name"].capitalize()
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

        # HOURLY_CONSUMPTION_SENSOR
        if self.hourly_consumption_sync_enabled:
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

        for sensor_key in sensor_list:
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
            for index, ele in enumerate(datasource[1:]):
                if not hasattr(data_obj, ele):
                    await entity.send_not_available()
                    self.logger.warning(
                        "%s - The object %s doesn't have the attribute %s. "
                        "Maybe your contract doesn't have this data ?",
                        sensor_key,
                        data_obj,
                        ele,
                    )
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
                await entity.send_not_available()
                self.logger.warning("Can not find value for: %s", sensor_key)
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
        # fetch consumption and wintercredits
        # if needed:
        await contract.get_periods_info()
        await contract.winter_credit.refresh_data()
        self.logger.info("Data fetched")

        # history
        if self.hourly_consumption_sync_enabled:
            await self.consumption_history_ent_switch.send_available()
            if self.is_consumption_history_syncing:
                await self.consumption_history_ent_switch.send_on()
            else:
                await self.consumption_history_ent_switch.send_off()

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
        return f"sensor.{entity_id}"

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

    async def start_history_task(self) -> None:
        """Start a asyncio task to fetch all the hourly data stored by HydroQc."""
        self.logger.info("Starting hourly consumption history sync task")
        # import ipdb;ipdb.set_trace()
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
        contract_info = await contract.get_info()
        # Get contract start date
        contract_start_date = datetime.date.fromisoformat(
            contract_info["dateDebutContrat"]
        )
        # Get two years ago plus few days
        today = datetime.date.today()
        oldest_data_date = today - datetime.timedelta(days=730)
        # Get the youngest date between contract start date VS 2 years ago
        start_date = (
            contract_start_date
            if contract_start_date > oldest_data_date
            else oldest_data_date
        )
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
        while data_date <= today:
            try:
                raw_data = await contract.get_hourly_consumption(data_date.isoformat())
            except hydroqc.error.HydroQcHTTPError as exp:
                if not self._got_first_hourly_consumption_data:
                    self.logger.info(
                        "There is not data for on %s."
                        "you can ignore the previous error message",
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
                data_date_str = data_date.isoformat()
                date_hour_str = data["heure"]
                stat["start"] = f"{data_date_str}T{date_hour_str}-04:00"
                # TODO handle consoHaut and consoReg
                stat["state"] = data["consoTotal"]
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
                # Connection
                try:
                    websocket = await client.ws_connect(
                        str(self._home_assistant_websocket_url)
                    )
                except aiohttp.client_exceptions.ClientConnectorError as exp:
                    raise Hydroqc2MqttWSError(
                        f"E0005: Error Websocket connection error - {exp.strerror}"
                    ) from exp

                response = await websocket.receive_json()
                if response.get("type") != "auth_required":
                    str_response = json.dumps(response)
                    raise Hydroqc2MqttWSError(
                        f"E0006: Bad server response: ${str_response}"
                    )

                # Auth
                await websocket.send_json(
                    {"type": "auth", "access_token": self._home_assistant_token}
                )
                response = await websocket.receive_json()
                if response.get("type") != "auth_ok":
                    raise Hydroqc2MqttWSError(
                        "E0007: Bad Home Assistant websocket token"
                    )
                # Get data from yesterday
                data_start_date_str = (
                    data_date - datetime.timedelta(days=1)
                ).isoformat()
                data_end_date_str = data_date.isoformat()

                await websocket.send_json(
                    {
                        "end_time": f"{data_end_date_str}T00:00:00-04:00",
                        "id": self._ws_query_id,
                        "period": "day",
                        "start_time": f"{data_start_date_str}T00:00:00-04:00",
                        "statistic_ids": [self.hourly_consumption_entity_id],
                        "type": "history/statistics_during_period",
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
                    raise Hydroqc2MqttWSError(
                        "E0008: Error trying to push consumption statistics"
                    )
                self.logger.debug(
                    "Successfully import consumption statistics for %s",
                    {data_end_date_str},
                )

        except Exception as exp:
            raise Hydroqc2MqttWSError(f"E0009: {exp}") from exp
