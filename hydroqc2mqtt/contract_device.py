import logging
from typing import Dict

from mqtt_hass_base.device import MqttDevice
from hydroqc.webuser import WebUser

from hydroqc2mqtt.__version__ import VERSION


SENSORS = {
    "balance": {"device_class": "monetary",
                # TODO: https://developers.home-assistant.io/docs/core/entity/#generic-properties
                #"entity_category": "???",
                "expire_after": 0,
                "force_update": False,
                "icon": "mdi:currency-usd",
                 # TODO validated: https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
                "state_class": "measurement",
                "unit": "$",
        }
    }
BINARY_SENSORS = {
    }

class HydroqcContractDevice(MqttDevice):

    def __init__(self, name: str, logger: logging.Logger, config: Dict):
        """Create a new MQTT Sensor Facebook object."""
        MqttDevice.__init__(self, name, logger)
        self._config = config
        self._webuser = WebUser(config["username"],
                                config["password"],
                                config.get("verify_ssl", True),
                                log_level=config.get("log_level", "WARNING"),
                                http_log_level=config.get("http_log_level", "WARNING")
                                )
        self.sw_version = VERSION
        self.manufacturer = "hydroqc"
        self._customer_id = str(self._config["customer"])
        self._account_id = str(config['account'])
        self._contract_id = str(config['contract'])
        connections = [
            ["customer", self._customer_id],
            ["account", self._account_id],
            ["contract", self._contract_id],
        ]
        for conn in connections:
            self.connections = conn
        self.identifiers = config['contract']
        self.name = f"hydroqc_{name}"

    def add_entities(self):
        """Add Home Assistant entities."""
        for sensor_name in self._config.get("sensors", []):
            if sensor_name not in SENSORS:
                raise
            entity_settings = SENSORS[sensor_name].copy()

            setattr(
                self,
                sensor_name,
                self.add_entity(
                    "sensor",
                    f"hydroqc_{self.name}_{sensor_name}",
                    entity_settings,
                ),
            )
        self.logger.info("added %s ...", self.name)

    async def update(self):
        """Update Home Assistant entities."""
        self.logger.info("Updating %s ...", self.name)
        # Fetch latest data
        await self._webuser.login()
        await self._webuser.get_info()
        # TODO fetch consumption and wintercredits
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)
        # Send sensor state one by one ...
        # TODO: Find a way to create a loop to reduce de code ...
        # Balance
        self.balance.send_state(account.balance, {})
        self.balance.send_available()
        self.logger.info("Updated %s ...", self.name)

    async def close(self):
        await self._webuser.close_session()
