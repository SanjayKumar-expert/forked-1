"""Mqtt Daemon module."""
import asyncio
import os
import re
import sys
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Any, TypedDict

import asyncio_mqtt as mqtt
import hydroqc
import yaml
from mqtt_hass_base.daemon import MqttClientDaemon
from mqtt_hass_base.error import MQTTHassBaseError

from hydroqc2mqtt.contract_device import (
    HydroqcContractConfigType,
    HydroqcContractDevice,
)
from hydroqc2mqtt.error import Hydroqc2MqttError, Hydroqc2MqttWSError

# TODO: python 3.11 => uncomment NotRequired
# from typing_extensions import NotRequired


MAIN_LOOP_WAIT_TIME = 60
OVERRIDE_REGEX = re.compile(
    # TODO add env
    (
        r"^HQ2M_CONTRACTS_(\d*)_("
        "USERNAME|"
        "PASSWORD|"
        "CUSTOMER|"
        "ACCOUNT|"
        "CONTRACT|"
        "NAME|"
        "LOG_LEVEL|"
        "HTTP_LOG_LEVEL|"
        "SYNC_HOURLY_CONSUMPTION_ENABLED|"
        "HOURLY_CONSUMPTION_SENSOR_NAME|"
        "SYNC_HOURLY_CONSUMPTION_HISTORY_ENABLED|"
        "HOME_ASSISTANT_WEBSOCKET_URL|"
        "HOME_ASSISTANT_TOKEN|"
        "PREHEAT_DURATION_MINUTES)$"
    )
)


# TODO: python 3.11 => remove total and uncomment NotRequired
class ConfigType(TypedDict, total=False):
    """Binary sensor entity settings dict format."""

    # sync_frequency: notrequired[int]
    # unregister_on_stop: notrequired[bool]
    sync_frequency: int
    unregister_on_stop: bool
    contracts: list[HydroqcContractConfigType]
    _main_loop_run_hour: int
    _hour_first_minute_loop: bool
    _main_loop_wait_time: int


class Hydroqc2Mqtt(MqttClientDaemon):
    """MQTT Sensor Feed."""

    def __init__(
        self,
        mqtt_host: str,
        mqtt_port: int,
        mqtt_username: str,
        mqtt_password: str,
        mqtt_discovery_root_topic: str,
        mqtt_data_root_topic: str,
        config_file: str,
        run_once: bool,
        log_level: str,
        http_log_level: str,
        hq_username: str,
        hq_password: str,
        hq_name: str,
        hq_customer_id: str,
        hq_account_id: str,
        hq_contract_id: str,
    ):  # pylint: disable=too-many-arguments
        """Create a new MQTT Hydroqc Sensor object."""
        self.contracts: list[HydroqcContractDevice] = []
        self.config_file = config_file
        self._run_once = run_once
        self._hq_username = hq_username
        self._hq_password = hq_password
        self._hq_name = hq_name
        self._hq_customer_id = hq_customer_id
        self._hq_account_id = hq_account_id
        self._hq_contract_id = hq_contract_id
        self._connected = False
        self._http_log_level = http_log_level
        self._needs_mqtt_reconnection: bool = False
        self.config: ConfigType = {}
        self._main_loop_run_hour = datetime.now().hour
        self._hour_first_minute_loop = False
        self._main_loop_wait_time = 0

        MqttClientDaemon.__init__(
            self,
            "hydroqc2mqtt",
            mqtt_host,
            mqtt_port,
            mqtt_username,
            mqtt_password,
            mqtt_discovery_root_topic,
            mqtt_data_root_topic,
            log_level,
        )

    def read_config(self) -> None:
        """Read env vars."""
        if self.config_file is None:
            self.config_file = os.environ.get("CONFIG_YAML", "config.yaml")
        if os.path.exists(self.config_file):
            with open(self.config_file, "rb") as fhc:
                self.config = yaml.safe_load(fhc)
        self.config.setdefault("contracts", [])

        # Override hydroquebec settings from env var if exists over config file
        config: dict[str, Any] = {}
        config["contracts"] = self.config["contracts"]

        # We ensure that os.environ.items() are sorted abc and with only needed env vars
        hq2m_env_vars = sorted(
            [env_var for env_var in os.environ if env_var.startswith("HQ2M_")]
        )
        for env_var in hq2m_env_vars:
            value = os.environ[env_var]
            if env_var == "HQ2M_SYNC_FREQUENCY":
                self.config["sync_frequency"] = int(value)
                continue
            match_res = OVERRIDE_REGEX.match(env_var)
            if match_res and len(match_res.groups()) == 2:
                index = int(match_res.group(1))
                # username|password|customer|account|contract|name
                kind = match_res.group(2).lower()
                # TODO improve me
                try:
                    # Check if the contracts is set in the config file
                    config["contracts"][index]
                except IndexError:
                    config["contracts"].append({})
                if env_var.endswith("_ENABLED"):
                    # Handle boolean values
                    config["contracts"][index][kind[: -len("_ENABLED")]] = (
                        value.lower() == "true"
                    )
                else:
                    config["contracts"][index][kind] = value

        if "http_log_level" not in config["contracts"][0] and self._http_log_level:
            config["contracts"][0]["http_log_level"] = self._http_log_level

        # Override hydroquebec settings
        if self._hq_username:
            config["contracts"][0]["username"] = self._hq_username
        if self._hq_password:
            config["contracts"][0]["password"] = self._hq_password
        if self._hq_name:
            config["contracts"][0]["name"] = self._hq_name
        if self._hq_customer_id:
            # Should be customer ?
            config["contracts"][0]["customer_id"] = self._hq_customer_id
        if self._hq_account_id:
            config["contracts"][0]["account_id"] = self._hq_account_id
        if self._hq_contract_id:
            config["contracts"][0]["contract_id"] = self._hq_contract_id

        self.config["contracts"] = config["contracts"]
        self.sync_frequency = int(
            self.config.get("sync_frequency", MAIN_LOOP_WAIT_TIME)
        )

        self.unregister_on_stop = bool(self.config.get("unregister_on_stop", False))

    async def _init_main_loop(self, stack: AsyncExitStack) -> None:
        """Init before starting main loop."""
        # Handle contracts
        for contract_config in self.config["contracts"]:
            contract = HydroqcContractDevice(
                contract_config["name"],
                self.logger,
                contract_config,
                self.mqtt_discovery_root_topic,
                self.mqtt_data_root_topic,
                self.mqtt_client,
            )

            self._connected = await contract.init_session()
            if not self._connected:
                self.logger.fatal(
                    "Can not start because we can not login at the startup."
                )
                sys.exit(1)

            await contract.add_entities()
            self.contracts.append(contract)

            # Register contract's entities to mqtt
            await contract.register()
            # Subscribes
            await contract.subscribe(self.tasks, stack)

    async def _main_loop(self, stack: AsyncExitStack) -> None:
        """Run main loop."""
        try:
            # Handle reconnection needed
            if self._needs_mqtt_reconnection:
                self.logger.info("Mqtt trying to reconnect")
                await self._mqtt_connect(stack)
                self.logger.info("Reinit contracts objects")
                for contract in self.contracts:
                    contract.set_mqtt_client(self.mqtt_client)
                self._needs_mqtt_reconnection = False

            # Connect to contracts
            for contract in self.contracts:
                await contract.init_session()

            # Get contract data
            for contract in self.contracts:
                await contract.update()

            # Sync_consumption_statistics
            for contract in self.contracts:
                if (
                    contract.hourly_consumption_sync_enabled
                    and not contract.is_consumption_history_syncing
                ):
                    await contract.sync_consumption_statistics()

        except hydroqc.error.HydroQcHTTPError as exp:
            self.logger.error("E0010: Hydroqc lib error: %s", exp)
        except Hydroqc2MqttWSError as exp:
            self.logger.error(exp)
        except Hydroqc2MqttError as exp:
            self.logger.error(exp)
        except (mqtt.MqttError, MQTTHassBaseError) as exp:
            self.logger.error("E0011: %s", exp)
            # Reconnect to Mqtt
            self._needs_mqtt_reconnection = True
            self.logger.warning("We will try to reconnect to MQTT server.")

        if self._run_once:
            self.must_run = False
            return

        if self._hour_first_minute_loop is True:
            self._hour_first_minute_loop = False
            self.logger.info("Ending first main loop of the hour.")
            self.logger.debug(
                "The main loop wait time is equal to %d", self._main_loop_wait_time
            )
        else:
            self._main_loop_wait_time = 0

        while self._main_loop_wait_time < self.sync_frequency and self.must_run:

            now_hour = datetime.now().hour
            if self._main_loop_run_hour != now_hour:
                self._hour_first_minute_loop = True
                self._main_loop_run_hour = now_hour
                self.logger.info("Starting first main loop of the hour.")
                break

            await asyncio.sleep(1)
            self._main_loop_wait_time += 1

    async def _loop_stopped(self) -> None:
        """Run after the end of the main loop."""
        for contract in self.contracts:
            await contract.close()

    async def _signal_handler(self, sig_name: str) -> None:
        """Handle SIGKILL."""
        if self.unregister_on_stop:
            for contract in self.contracts:
                await contract.unregister()

    async def _on_disconnect(
        self,
    ) -> None:
        """MQTT on disconnect callback."""
