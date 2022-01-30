import asyncio
import os

import yaml

from mqtt_hass_base.daemon import MqttClientDaemon
from hydroqc2mqtt.contract_device import HydroqcContractDevice


MAIN_LOOP_WAIT_TIME = 300


class Hydroqc2Mqtt(MqttClientDaemon):
    """MQTT Sensor Feed."""

    def __init__(self):
        """Create a new MQTT Hydroqc Sensor object."""
        self.contracts = []
        MqttClientDaemon.__init__(self, "hydroqc2mqtt")

    def read_config(self):
        """Read env vars."""
        self.config_file = os.environ["CONFIG_YAML"]
        with open(self.config_file, "rb") as fhc:
            self.config = yaml.safe_load(fhc)
        self.sync_frequency = int(
            self.config.get("sync_frequency", MAIN_LOOP_WAIT_TIME)
        )
        # Handle contracts
        for contract_config in self.config['contracts']:
            contract = HydroqcContractDevice(
                    contract_config['name'],
                    self.logger,
                    contract_config
                    )
            contract.add_entities()
            self.contracts.append(contract)

    async def _init_main_loop(self):
        """Init before starting main loop."""
        for contract in self.contracts:
            contract.set_mqtt_client(self.mqtt_client) 

    async def _main_loop(self):
        """Run main loop."""
        for contract in self.contracts:
            await contract.update()

        i = 0
        while i < self.sync_frequency and self.must_run:
            await asyncio.sleep(1)
            i += 1

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT on connect callback."""
        for contract in self.contracts:
            contract.register()

    def _on_publish(self, client, userdata, mid):
        """MQTT on publish callback."""

    def _mqtt_subscribe(self, client, userdata, flags, rc):
        """Subscribe to all needed MQTT topic."""

    def _signal_handler(self, signal_, frame):
        """Handle SIGKILL."""
        for contract in self.contracts:
            contract.unregister()

    def _on_message(self, client, userdata, msg):
        """Do nothing."""

    async def _loop_stopped(self):
        """Run after the end of the main loop."""
        for contract in self.contracts:
            contract.close()
