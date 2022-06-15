"""Mqtt Daemon module."""
import asyncio
import time
import sys
import os
import re
from types import FrameType
from typing import Any, Dict, Optional, List, TypedDict

# TODO: python 3.11 => uncomment NotRequired
# from typing_extensions import NotRequired

import paho.mqtt.client as mqtt

import yaml

from mqtt_hass_base.daemon import MqttClientDaemon
from hydroqc2mqtt.contract_device import (
    HydroqcContractDevice,
    HydroqcContractConfigType,
)


MAIN_LOOP_WAIT_TIME = 300
OVERRIDE_REGEX = re.compile(
    r"HQ2M_CONTRACTS_(\d*)_" "(USERNAME|PASSWORD|CUSTOMER|ACCOUNT|CONTRACT|NAME)"
)


# TODO: python 3.11 => remove total and uncomment NotRequired
class ConfigType(TypedDict, total=False):
    """Binary sensor entity settings dict format."""

    # sync_frequency: notrequired[int]
    # unregister_on_stop: notrequired[bool]
    sync_frequency: int
    unregister_on_stop: bool
    contracts: List[HydroqcContractConfigType]


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
        hq_username: str,
        hq_password: str,
        hq_name: str,
        hq_customer_id: str,
        hq_account_id: str,
        hq_contract_id: str,
    ):  # pylint: disable=too-many-arguments
        """Create a new MQTT Hydroqc Sensor object."""
        self.contracts: List[HydroqcContractDevice] = []
        self.config_file = config_file
        self._run_once = run_once
        self._hq_username = hq_username
        self._hq_password = hq_password
        self._hq_name = hq_name
        self._hq_customer_id = hq_customer_id
        self._hq_account_id = hq_account_id
        self._hq_contract_id = hq_contract_id
        self._connected = False
        self.config: ConfigType = {}

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
        config: Dict[str, Any] = {}
        config["contracts"] = self.config["contracts"]
        # if config["contracts"] is None:
        #    config["contracts"] = []

        # TODO we should ensure that  os.environ.items() are sorted abc...
        for env_var, value in os.environ.items():
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
                config["contracts"][index][kind] = value
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
        # Handle contracts
        for contract_config in self.config["contracts"]:
            contract = HydroqcContractDevice(
                contract_config["name"],
                self.logger,
                contract_config,
                self.mqtt_discovery_root_topic,
                self.mqtt_data_root_topic,
            )
            contract.add_entities()
            self.contracts.append(contract)

    async def _set_devices_mqtt_client(self) -> None:
        """Set mqtt_client to all devices."""
        for contract in self.contracts:
            contract.set_mqtt_client(self.mqtt_client)

    async def _init_main_loop(self) -> None:
        """Init before starting main loop."""
        for contract in self.contracts:
            self._connected = await contract.init_session()
            if not self._connected:
                self.logger.fatal(
                    "Can not start because we can not login at the startup."
                )
                sys.exit(1)

    async def _main_loop(self) -> None:
        """Run main loop."""
        # TODO refreshing session using a setting in the config yaml file
        for contract in self.contracts:
            await contract.init_session()

        for contract in self.contracts:
            await contract.update()

        if self._run_once:
            self.must_run = False
            return

        i = 0
        while i < self.sync_frequency and self.must_run:
            await asyncio.sleep(1)
            i += 1

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Optional[dict[str, Any]],
        flags: dict[str, Any],
        rc: int,
    ) -> None:
        """MQTT on connect callback."""
        while not self._connected:
            self.logger.info("Waiting for the HydroQC connection.")
            time.sleep(1)

        for contract in self.contracts:
            contract.register()

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Optional[Dict[str, Any]],
        rc: int,  # pylint: disable=invalid-name
    ) -> None:
        """MQTT on disconnect callback."""

    def _on_publish(
        self, client: mqtt.Client, userdata: Optional[dict[str, Any]], mid: int
    ) -> None:
        """MQTT on publish callback."""

    def _mqtt_subscribe(
        self,
        client: mqtt.Client,
        userdata: Optional[dict[str, Any]],
        flags: dict[str, Any],
        rc: int,
    ) -> None:
        """Subscribe to all needed MQTT topic."""

    def _signal_handler(self, signal_: int, frame: FrameType) -> None:
        """Handle SIGKILL."""
        if self.unregister_on_stop:
            for contract in self.contracts:
                contract.unregister()

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Optional[dict[str, Any]],
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Do nothing."""

    async def _loop_stopped(self) -> None:
        """Run after the end of the main loop."""
        for contract in self.contracts:
            await contract.close()
