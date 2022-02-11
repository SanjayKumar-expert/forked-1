import logging
from typing import Dict

from mqtt_hass_base.device import MqttDevice
from hydroqc.webuser import WebUser
import hydroqc

from hydroqc2mqtt.__version__ import VERSION
from hydroqc2mqtt.sensors import SENSORS, BINARY_SENSORS


class HydroqcContractDevice(MqttDevice):
    def __init__(self, name: str, logger: logging.Logger, config: Dict):
        """Create a new MQTT Sensor Facebook object."""
        MqttDevice.__init__(self, name, logger)
        self._config = config
        self._webuser = WebUser(
            config["username"],
            config["password"],
            config.get("verify_ssl", True),
            log_level=config.get("log_level", "WARNING"),
            http_log_level=config.get("http_log_level", "WARNING"),
        )
        self.sw_version = VERSION
        self.manufacturer = "hydroqc"
        self._customer_id = str(self._config["customer"])
        self._account_id = str(config["account"])
        self._contract_id = str(config["contract"])
        connections = [
            ["customer", self._customer_id],
            ["account", self._account_id],
            ["contract", self._contract_id],
        ]
        for conn in connections:
            self.connections = conn
        self.identifiers = config["contract"]
        self._base_name = name
        self.name = f"hydroqc_{self._base_name}"

    def add_entities(self):
        """Add Home Assistant entities."""
        if "sensors" in self._config:
            sensor_list = self._config["sensors"]
        else:
            sensor_list = SENSORS.keys()
        for sensor_key in sensor_list:
            if sensor_key not in SENSORS:
                raise
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
                self.add_entity(
                    "sensor",
                    sensor_name,
                    f"{self._contract_id}-{sensor_name}",
                    entity_settings,
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                ),
            )

        if "binary_sensors" in self._config:
            sensor_list = self._config["binary_sensors"]
        else:
            sensor_list = BINARY_SENSORS.keys()
        for sensor_key in sensor_list:
            if sensor_key not in BINARY_SENSORS:
                raise
            entity_settings = BINARY_SENSORS[sensor_key].copy()
            sensor_name = entity_settings["name"].capitalize()
            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del entity_settings["data_source"]
            del entity_settings["name"]
            del entity_settings["sub_mqtt_topic"]
            entity_settings["object_id"] = f"{self.name}_{sensor_name}"

            setattr(
                self,
                sensor_key,
                self.add_entity(
                    "binarysensor",
                    sensor_name,
                    f"{self._contract_id}-{sensor_name}",
                    entity_settings,
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}",
                ),
            )
        self.logger.info("added %s ...", self.name)

    async def init_session(self):
        if self._webuser.session_expired:
            self.logger.info("Login")
            await self._webuser.login()
        else:
            try:
                await self._webuser.refresh_session()
                self.logger.info("Refreshing session")
            except hydroqc.error.HydroQcHTTPError:
                # Try to login if the refresh session didn't work
                self.logger.info("Refreshing session failed, try to login")
                await self._webuser.login()

    async def update(self):
        """Update Home Assistant entities."""
        self.logger.info("Updating %s ...", self.name)
        # TODO if any api calls failed, we should NOT crash and set sensors to not_available
        # Fetch latest data
        await self._webuser.get_info()
        # fetch consumption and wintercredits
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)
        await contract.get_periods_info()
        await contract.winter_credit.refresh_data()
        # Send sensor state one by one ...
        for sensor_key in self._config.get("sensors", []):
            datasource = SENSORS[sensor_key]["data_source"].split(".")
            data_obj = locals()[datasource[0]]
            value = None
            for index, el in enumerate(datasource[1:]):
                data_obj = getattr(data_obj, el)
                # If it's the last element of the datasource then it's the value
                if index + 1 == len(datasource[1:]):
                    value = data_obj

            entity = getattr(self, sensor_key)
            if value is None:
                entity.send_available()
                self.logger.warning("Can not find value for: %s", sensor_key)
            else:
                entity.send_state(value, {})
                entity.send_available()

        for sensor_key in self._config.get("binary_sensors", []):
            datasource = BINARY_SENSORS[sensor_key]["data_source"].split(".")
            data_obj = locals()[datasource[0]]
            value = None
            for index, el in enumerate(datasource[1:]):
                data_obj = getattr(data_obj, el)
                # If it's the last element of the datasource then it's the value
                if index + 1 == len(datasource[1:]):
                    value = "ON" if data_obj else "OFF"

            entity = getattr(self, sensor_key)
            if value is None:
                entity.send_available()
                self.logger.warning("Can not find value for: %s", sensor_key)
            else:
                entity.send_state(value, {})
                entity.send_available()

        self.logger.info("Updated %s ...", self.name)

    async def close(self):
        await self._webuser.close_session()
