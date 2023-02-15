"""Module defining HydroQC Contract."""
import asyncio
import copy
import datetime
import json
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, TypedDict, cast

import aiohttp
import hydroqc
from dateutil.relativedelta import relativedelta
from homeassistant.util import slugify
from hydroqc.contract.common import Contract
from mqtt_hass_base.entity import (
    MqttButton,
    MqttNumber,
    MqttSensor,
    MqttSwitch,
    SensorSettingsType,
    SwitchSettingsType,
)
from packaging import version
from pytz import timezone

import hydroqc2mqtt.sensors
from hydroqc2mqtt.error import Hydroqc2MqttError, Hydroqc2MqttWSError
from hydroqc2mqtt.sensors import (
    HOURLY_CONSUMPTION_CLEAR_BUTTON,
    HOURLY_CONSUMPTION_HISTORY_DAYS,
    HOURLY_CONSUMPTION_HISTORY_SWITCH,
)

if TYPE_CHECKING:
    from hydroqc2mqtt.contract_device import HydroqcContractDevice


TZ_EASTERN = timezone("US/Eastern")


class HAEnergyStatType(TypedDict):
    """Home Assistant energy hourly stat dict format."""

    start: str
    state: float
    sum: float


class HourlyConsumpHandler:
    """Handler for Hourly consumption statistics."""

    def __init__(
        self,
        name: str,
        enabled: bool,
        home_assistant_websocket_url: str,
        home_assistant_token: str,
        logger: logging.Logger,
        contract: "HydroqcContractDevice",
    ):
        """Construct Handler."""
        self._ws_query_id = 1
        self.name = name
        self._enabled = enabled
        self._home_assistant_websocket_url: str = home_assistant_websocket_url
        self._home_assistant_token: str = home_assistant_token
        self._sync_hourly_consumption_history_task: asyncio.Task[None] | None = None
        self._got_first_hourly_consumption_data: bool = False
        self.hourly_consumption_entity_list: dict[str, MqttSensor] = {}
        self.logger = logger.getChild("HCH")
        self._contract = contract

    @property
    def enabled(self) -> bool:
        """Is hourly consumption sync enabled."""
        return self._enabled

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
        # HOURLY_CONSUMPTION_SENSOR
        if not self.enabled:
            self.logger.info("Consumption sync disabled")
            return

        self.logger.info("Consumption sync enabled")
        for consumption_type in self._contract.consumption_types:
            entity_settings = getattr(
                hydroqc2mqtt.sensors,
                f"HOURLY_CONSUMPTION_{consumption_type.upper()}_SENSOR",
            ).copy()
            sensor_name = entity_settings["name"].capitalize()
            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del entity_settings["name"]
            del entity_settings["sub_mqtt_topic"]
            entity_settings["object_id"] = self.get_hourly_consumption_entity_id(
                consumption_type
            )

            self.hourly_consumption_entity_list[consumption_type] = cast(
                MqttSensor,
                self._contract.add_entity(
                    "sensor",
                    sensor_name,
                    f"{self._contract._contract_id}-{sensor_name}",
                    cast(SensorSettingsType, entity_settings),
                    sub_mqtt_topic=f"{self._contract._base_name}/{sub_mqtt_topic}",
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
            self._contract.add_entity(
                "number",
                sensor_name,
                f"{self._contract._contract_id}-{sensor_name}",
                cast(SwitchSettingsType, number_entity_settings),
                sub_mqtt_topic=f"{self._contract._base_name}/{sub_mqtt_topic}",
                subscriptions={"command_topic": self._contract._command_callback},
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
            self._contract.add_entity(
                "switch",
                sensor_name,
                f"{self._contract._contract_id}-{sensor_name}",
                cast(SwitchSettingsType, switch_entity_settings),
                sub_mqtt_topic=f"{self._contract._base_name}/{sub_mqtt_topic}",
                subscriptions={"command_topic": self._contract._command_callback},
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
            self._contract.add_entity(
                "button",
                sensor_name,
                f"{self._contract._contract_id}-{sensor_name}",
                cast(SwitchSettingsType, button_entity_settings),
                sub_mqtt_topic=f"{self._contract._base_name}/{sub_mqtt_topic}",
                subscriptions={"command_topic": self._contract._command_callback},
            ),
        )

        self.logger.info("added %s ...", self.name)

    async def update(self) -> None:
        """Update Home Assistant entities."""
        self.logger.info("Updating ...")
        # history
        await self.consumption_history_ent_switch.send_available()
        if self.is_consumption_history_syncing:
            await self.consumption_history_ent_switch.send_on()
        else:
            await self.consumption_history_ent_switch.send_off()

        await self.consumption_clear_ent_button.send_available()
        await self.consumption_history_ent_number.send_available()

        self.logger.info("Updated %s ...", self.name)

    def get_hourly_consumption_entity_id(
        self, consumption_type: str, with_entity_type: bool = False
    ) -> str:
        """Get the entity_id of the Hourly consumption HA sensor."""
        entity_id = f"{self.name}_{consumption_type}_hourly_consumption"
        if with_entity_type:
            return "sensor." + slugify(entity_id)
        return slugify(entity_id)

    async def sync_consumption_statistics(self) -> None:
        """Sync hourly consumption statistics.

        It synchronizes all the hourly data of yesterday and today.
        """
        if not self.enabled:
            return

        if self.is_consumption_history_syncing:
            # Historical stats currently syncing
            # So we do nothing
            return

        _, _, contract = await self._contract.get_contract()
        # We send data for today and yesterday to be sure to not miss and data
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        await self.get_historical_statistics(contract, yesterday)
        for entity in self.hourly_consumption_entity_list.values():
            await entity.send_available()

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
        for consumption_type in self._contract.consumption_types:
            hourly_consumption_entity_id = self.get_hourly_consumption_entity_id(
                consumption_type, True
            )
            async with aiohttp.ClientSession() as client:
                websocket, _ = await self.connect_hass_ws(client)

                await websocket.send_json(
                    {
                        "id": self._ws_query_id,
                        "statistic_ids": [hourly_consumption_entity_id],
                        "type": "recorder/clear_statistics",
                    }
                )
                response = await websocket.receive_json()
                if response.get("success") is not True:
                    reason = response.get("error", {}).get("message", "Unknown")
                    raise Hydroqc2MqttWSError(
                        f"E0008: Error trying to clear consumption statistics - Reason: {reason}"
                    )
                self._ws_query_id += 1
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
        print("FFFFFF1")
        _, _, contract = await self._contract.get_contract()
        print("FFFFFF1")
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
        await self.get_historical_csv_statistics(contract, start_date)
        await self.consumption_history_ent_switch.send_off()
        self.logger.info("Hourly consumption history sync done.")

    async def get_historical_csv_statistics(
        self, contract: Contract, start_data_date: datetime.date
    ) -> None:
        """Fetch hourly data from a specific day to today and send it to Home Assistant.

        It synchronizes all the hourly data of the data_date
        - from HydroQc (the contract CSV functions of the hydroqc lib)
        - to Home assistant using websocket

        Note: it used only for "historical consumption"
        """
        today = datetime.date.today()
        # We have 5 tries to fetch all historical data
        retry = 5
        self._got_first_hourly_consumption_data = False
        data_date = copy.copy(start_data_date)
        stats: dict[str, list[HAEnergyStatType]] = {
            "reg": [],
            "haut": [],
            "total": [],
        }
        start_date = None
        while data_date < today:
            try:
                self.logger.info(
                    "Fetching hourly consumption for period starting on %s",
                    data_date.isoformat(),
                )
                raw_data = cast(
                    Iterator[list[str | int | float]],
                    await contract.get_hourly_energy(data_date, today),
                )
            except Exception as exp:
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
                    await self._contract._login()
                    # await self.
                    retry -= 1
                    continue

                self.logger.error(
                    "Error getting historical consumption data on %s. Stopping import",
                    data_date.isoformat(),
                )
                raise Hydroqc2MqttError(f"E0010: {exp}") from exp

            self._got_first_hourly_consumption_data = True
            # First line is the header
            raw_data_sorted = list(raw_data)
            # header = raw_data_sorted[0]
            # Header is (D, D_CPC)
            # ['Contrat', 'Date et heure',
            #  'kWh',
            #  'Code de consommation', 'Température moyenne (°C)', 'Code de température']
            # Or (DT, DPC)
            # ['Contrat', 'Date et heure',
            #  'kWh bas', 'kWh Haut',
            #  'Code de consommation', 'Température moyenne (°C)', 'Code de température']
            raw_data_sorted = raw_data_sorted[1:]
            raw_data_sorted.reverse()

            # stats: list[HAEnergyStatType] = []
            for line in raw_data_sorted:
                # Get date
                date_str = cast(str, line[1])
                data_datetime = TZ_EASTERN.localize(
                    datetime.datetime.fromisoformat(date_str)
                )
                if start_date is None:
                    start_date = data_datetime
                # Get consumption
                if self._contract.rate in {"DT", "DPC"}:
                    _, _, reg_cptn_str, high_cptn_str, _, _, _ = [
                        str(ele) for ele in line
                    ]
                    reg_consumption = (
                        float(reg_cptn_str.replace(",", ".")) if reg_cptn_str else 0
                    )
                    stats["reg"].append(
                        {
                            "sum": 0,
                            "state": reg_consumption,
                            "start": data_datetime.isoformat(),
                        }
                    )
                    haut_consumption = (
                        float(high_cptn_str.replace(",", ".")) if high_cptn_str else 0
                    )
                    stats["haut"].append(
                        {
                            "sum": 0,
                            "state": haut_consumption,
                            "start": data_datetime.isoformat(),
                        }
                    )
                    total_consumption = reg_consumption + haut_consumption
                    stats["total"].append(
                        {
                            "sum": 0,
                            "state": total_consumption,
                            "start": data_datetime.isoformat(),
                        }
                    )
                    self.logger.debug(
                        "%s - total: %s - reg: %s - haut: %s",
                        stats["total"][-1]["start"],
                        stats["total"][-1]["state"],
                        stats["reg"][-1]["state"],
                        stats["haut"][-1]["state"],
                    )
                else:
                    _, date_str, cptn_str, _, _, _ = [str(ele) for ele in line]
                    total_consumption = (
                        float(cptn_str.replace(",", ".")) if cptn_str else 0
                    )
                    stats["total"].append(
                        {
                            "sum": 0,
                            "state": total_consumption,
                            "start": data_datetime.isoformat(),
                        }
                    )
                    self.logger.debug(
                        "%s - total - %s",
                        stats["total"][-1]["start"],
                        stats["total"][-1]["state"],
                    )

            data_date = data_datetime.date() + datetime.timedelta(days=1)

        if start_date is None:
            raise Hydroqc2MqttError("EOO11: no Start date found while importing data.")
        for consumption_type, stat in stats.items():
            if not stat:
                # Ignore empty stats list
                continue
            await self.send_consumption_statistics(
                stat, consumption_type, start_date.date()
            )

    async def get_historical_statistics(
        self, contract: Contract, data_date: datetime.date
    ) -> None:
        """Fetch hourly data from a specific day to today and send it to Home Assistant.

        It synchronizes all the hourly data of the data_date
        - from HydroQc (using hydroqc lib)
        - to Home assistant using websocket

        Note: it used only for "live consumption"
        """
        today = datetime.date.today()
        # We have 5 tries to fetch all historical data
        retry = 3
        self._got_first_hourly_consumption_data = False
        while data_date <= today:
            try:
                raw_data = await contract.get_hourly_consumption(data_date)
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
                    await asyncio.sleep(3)
                    self.logger.warning(
                        "Retrying to sync all historical data on %s (%s/5)",
                        data_date.isoformat(),
                        retry,
                    )
                    await self._contract._login()
                    retry -= 1
                    continue

                self.logger.error(
                    "Error getting historical consumption data on %s. Stopping import",
                    data_date.isoformat(),
                )
                raise Hydroqc2MqttError(f"E0004: {exp}") from exp

            for consumption_type in self._contract.consumption_types:
                self._got_first_hourly_consumption_data = True
                stats: list[HAEnergyStatType] = []
                for data in raw_data["results"]["listeDonneesConsoEnergieHoraire"]:
                    stat: HAEnergyStatType = {"start": "", "state": 0, "sum": 0}
                    hour_splitted: list[int] = [
                        int(e) for e in data["heure"].split(":", 2)
                    ]
                    start_date = datetime.datetime.combine(
                        data_date,
                        datetime.time(
                            hour_splitted[0], hour_splitted[1], hour_splitted[2]
                        ),
                    )
                    localized_start_date = TZ_EASTERN.localize(start_date)
                    stat["start"] = localized_start_date.isoformat()
                    key_csptn = f"conso{consumption_type.capitalize()}"
                    if key_csptn not in ("consoReg", "consoHaut", "consoTotal"):
                        raise Hydroqc2MqttWSError("E0012: bad data key {key_csptn}")
                    stat["state"] = data[key_csptn]  # type:ignore
                    self.logger.debug(
                        "%s - %s - %s", stat["start"], consumption_type, stat["state"]
                    )
                    stats.append(stat)

                await self.send_consumption_statistics(
                    stats, consumption_type, data_date
                )

            data_date += datetime.timedelta(days=1)
        self.logger.info("Success - hourly consumption sync task")

    async def send_consumption_statistics(
        self,
        stats: list[HAEnergyStatType],
        consumption_type: str,
        data_date: datetime.date,
    ) -> None:
        """Send all hourly data of a whole day to Home Assistant.

        It uses websocket to send data to Home Assistant
        """
        # the consumption data are relative to the 00:00:00 of the give day
        if not self.enabled:
            return
        self._ws_query_id = 1
        try:
            hourly_consumption_entity_id = self.get_hourly_consumption_entity_id(
                consumption_type, True
            )
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
                self.logger.debug(
                    "Trying to get statistics of %s on %s",
                    hourly_consumption_entity_id,
                    data_start_date_str,
                )
                await websocket.send_json(
                    {
                        "end_time": data_end_date_str,
                        "id": self._ws_query_id,
                        "period": "day",
                        "start_time": data_start_date_str,
                        "statistic_ids": [hourly_consumption_entity_id],
                        "type": websocket_call_type,
                    }
                )
                self._ws_query_id += 1
                response = await websocket.receive_json()
                self.logger.debug(
                    "Got statistics of %s on %s: %s",
                    hourly_consumption_entity_id,
                    data_start_date_str,
                    response,
                )
                if not response.get("result"):
                    base_sum = 0
                else:
                    # Get sum from response
                    base_sum = response["result"][hourly_consumption_entity_id][-1][
                        "sum"
                    ]
                # Add sum from last yesterday's data
                for index, stat in enumerate(stats):
                    if index == 0:
                        stat["sum"] = round(base_sum + stat["state"], 2)
                    else:
                        stat["sum"] = round(stat["state"] + stats[index - 1]["sum"], 2)

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
                            "statistic_id": hourly_consumption_entity_id,
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
                        f"E0013: Error trying to push consumption statistics - Reason: {reason}"
                    )
                self.logger.debug(
                    "Successfully import consumption statistics for %s",
                    {data_end_date_str},
                )

        except Exception as exp:
            raise Hydroqc2MqttWSError(f"E0009: {exp}") from exp
