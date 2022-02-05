import logging
from typing import Dict

from mqtt_hass_base.device import MqttDevice
from hydroqc.webuser import WebUser

from hydroqc2mqtt.__version__ import VERSION


SENSORS = {
    "balance": {
        "name": "Balance",
        "data_source": "account.balance",
        "device_class": "monetary",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "state_class": "measurement",
        "unit": "$",
        "sub_mqtt_topic": "acccount/state",
    },
    "wc_cumulated_credit": {
        "name": "Cumulated Winter Credit",
        "data_source": "contract.winter_credit.value_cumulated_credit",
        "device_class": "monetary",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:currency-usd",
        "state_class": "measurement",
        "unit": "$",
        "sub_mqtt_topic": "wintercredits/state",
    },
    "wc_next_anchor_start": {
        "name": "Next Anchor Period Start",
        "data_source": "contract.winter_credit.value_next_periods_anchor_start_iso",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/next/anchor",

    },
    "wc_next_anchor_end": {
        "name": "Next Anchor Period End",
        "data_source": "contract.winter_credit.value_next_periods_anchor_end_iso",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "wintercredits/next/anchor",

    },
    "wc_next_peak_start": {
        "name": "Next Peak Period Start",
        "data_source": "contract.winter_credit.value_next_periods_peak_start_iso",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/next/peak",

    },
    "wc_next_peak_end": {
        "name": "Next Peak Period End",
        "data_source": "contract.winter_credit.value_next_periods_peak_end_iso",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "wintercredits/next/peak",

    },
    "wc_next_critical_event_start": {
        "name": "Next Critical Event Start",
        "data_source": "contract.winter_credit.value_next_start_iso",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-start",
        "sub_mqtt_topic": "wintercredits/next/event",
    },
    "wc_next_critical_event_end": {
        "name": "Next Critical Event End",
        "data_source": "contract.winter_credit.value_next_end_iso",
        "device_class": "timestamp",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:clock-end",
        "sub_mqtt_topic": "wintercredits/next/event",
    }
}
BINARY_SENSORS = {
    "wc_critical": {
        "name" : "Critical",
        "data_source": "contract.winter_credit.value_state_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
    },
    "wc_event_in_progress": {
        "name": "Event In Progress",
        "data_source": "contract.winter_credit.value_state_event_in_progress",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
    },
    "wc_pre_heat": {
        "name": "Pre-heat In Progress",
        "data_source": "contract.winter_credit.value_state_pre_heat",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
    },
    "wc_next_anchor_critical": {
        "name": "Next Anchor Period Critical",
        "data_source": "contract.winter_credit.value_next_periods_anchor_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
    },
    "wc_next_peak_critical": {
        "name": "Next Peak Period Critical",
        "data_source": "contract.winter_credit.value_next_periods_peak_critical",
        "expire_after": 0,
        "force_update": False,
        "icon": "mdi:flash-alert",
        "sub_mqtt_topic": "wintercredits/state",
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
        self._base_name = name
        self.name = f"hydroqc_{self._base_name}"

    def add_entities(self):
        """Add Home Assistant entities."""
        for sensor_key in self._config.get("sensors", []):
            if sensor_key not in SENSORS:
                raise
            entity_settings = SENSORS[sensor_key].copy()
            sensor_name = entity_settings["name"].lower()
            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del(entity_settings["data_source"])
            del(entity_settings["name"])
            del(entity_settings["sub_mqtt_topic"])

            setattr(
                self,
                sensor_key,
                self.add_entity(
                    "sensor",
                    f"{self.name}_{sensor_name}",
                    entity_settings,
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}"
                ),
            )
        for sensor_key in self._config.get("binary_sensors", []):
            if sensor_key not in BINARY_SENSORS:
                raise
            entity_settings = BINARY_SENSORS[sensor_key].copy()
            sensor_name = entity_settings["name"].lower()
            sub_mqtt_topic = entity_settings["sub_mqtt_topic"].lower().strip("/")
            del(entity_settings["data_source"])
            del(entity_settings["name"])
            del(entity_settings["sub_mqtt_topic"])

            setattr(
                self,
                sensor_key,
                self.add_entity(
                    "binarysensor",
                    f"{self.name}_{sensor_name}",
                    entity_settings,
                    sub_mqtt_topic=f"{self._base_name}/{sub_mqtt_topic}"
                ),
            )
        self.logger.info("added %s ...", self.name)

    async def init_session(self):
        if self._webuser.session_expired:
            print("LOGIN")
            await self._webuser.login()
        else:
            print("REFRESH")
            await self._webuser.refresh_session()

    async def update(self):
        """Update Home Assistant entities."""
        self.logger.info("Updating %s ...", self.name)
        # Fetch latest data
        await self._webuser.get_info()
        # TODO fetch consumption and wintercredits
        customer = self._webuser.get_customer(self._customer_id)
        account = customer.get_account(self._account_id)
        contract = account.get_contract(self._contract_id)
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
            if value is None:
                raise Exception("Can not find value")

            entity = getattr(self, sensor_key)
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
            if value is None:
                raise Exception("Can not find value")

            entity = getattr(self, sensor_key)
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
