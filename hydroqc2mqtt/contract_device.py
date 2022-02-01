import logging
from typing import Dict

from mqtt_hass_base.device import MqttDevice
from hydroqc.webuser import WebUser

from hydroqc2mqtt.__version__ import VERSION


SENSORS = {
    "balance": {
        "data_source": "account.balance",
        #"data_source": "contract.winter_credit.contract_id",
        # https://www.home-assistant.io/integrations/sensor/#device-class
        "device_class": "monetary",
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
    "wc_critical": {
        "data_source": "contract.winter_credit.value_state_critical",
        # https://www.home-assistant.io/integrations/binary_sensor/#device-class
        # "device_class": "running",
        # TODO: https://developers.home-assistant.io/docs/core/entity/#generic-properties
        #"entity_category": "???",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
    }
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
            del(entity_settings["data_source"])

            setattr(
                self,
                sensor_name,
                self.add_entity(
                    "sensor",
                    f"{self.name}_{sensor_name}",
                    entity_settings,
                ),
            )
        for sensor_name in self._config.get("binary_sensors", []):
            if sensor_name not in BINARY_SENSORS:
                raise
            entity_settings = BINARY_SENSORS[sensor_name].copy()
            del(entity_settings["data_source"])

            setattr(
                self,
                sensor_name,
                self.add_entity(
                    "binarysensor",
                    f"{self.name}_{sensor_name}",
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
        await contract.winter_credit.refresh_data()
        # Send sensor state one by one ...
        for sensor_name in self._config.get("sensors", []):
            datasource = SENSORS[sensor_name]["data_source"].split(".")
            data_obj = locals()[datasource[0]]
            value = None
            for index, el in enumerate(datasource[1:]):
                data_obj = getattr(data_obj, el)
                # If it's the last element of the datasource then it's the value
                if index + 1 == len(datasource[1:]):
                    value = data_obj
            if value is None:
                raise Exception("Can not find value")

            entity = getattr(self, sensor_name)
            entity.send_state(value, {})
            entity.send_available()


        for sensor_name in self._config.get("binary_sensors", []):
            datasource = BINARY_SENSORS[sensor_name]["data_source"].split(".")
            data_obj = locals()[datasource[0]]
            value = None
            for index, el in enumerate(datasource[1:]):
                data_obj = getattr(data_obj, el)
                # If it's the last element of the datasource then it's the value
                if index + 1 == len(datasource[1:]):
                    value = "ON" if data_obj else "OFF"
            if value is None:
                raise Exception("Can not find value")

            entity = getattr(self, sensor_name)
            entity.send_state(value, {})
            entity.send_available()
        # TODO: Find a way to create a loop to reduce de code ...
        # Balance
        #self.balance.send_state(account.balance, {})
        #self.balance.send_available()
        # Winter credit critical
        #self.wc_critical.send_state(bool(contract.whc.critical))
        #self.wc_critical.send_available()
        self.logger.info("Updated %s ...", self.name)

    async def close(self):
        await self._webuser.close_session()
