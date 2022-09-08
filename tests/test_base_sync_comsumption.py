"""Base tests for hydroqc2mqtt."""
import base64
import json
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import paho.mqtt.client as mqtt
from aioresponses import aioresponses
from hydroqc.hydro_api.consts import (
    AUTH_URL,
    AUTHORIZE_URL,
    CUSTOMER_INFO_URL,
    GET_WINTER_CREDIT_API_URL,
    HOURLY_CONSUMPTION_API_URL,
    LOGIN_URL_6,
    PERIOD_DATA_URL,
    PORTRAIT_URL,
    RELATION_URL,
    SECURITY_URL,
    SESSION_REFRESH_URL,
    SESSION_URL,
)
from websocket_server import WebSocketHandler, WebsocketServer  # type: ignore

from hydroqc2mqtt.__main__ import main
from hydroqc2mqtt.__version__ import VERSION

CONTRACT_ID = os.environ["HQ2M_CONTRACTS_0_CONTRACT"]
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", None)
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", None)
MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ["MQTT_PORT"])
MQTT_DISCOVERY_ROOT_TOPIC = os.environ.get(
    "MQTT_DISCOVERY_ROOT_TOPIC", os.environ.get("ROOT_TOPIC", "homeassistant")
)
MQTT_DATA_ROOT_TOPIC = os.environ.get("MQTT_DATA_ROOT_TOPIC", "homeassistant")

WS_SERVER_HOST = "127.0.0.1"
WS_SERVER_PORT = 18123
WS_SERVER_URL = f"http://{WS_SERVER_HOST}:{WS_SERVER_PORT}"

TODAY = datetime.today()
YESTERDAY = TODAY - timedelta(days=1)
YESTERDAY2 = TODAY - timedelta(days=2)
TODAY_STR = TODAY.strftime("%Y-%m-%d")
YESTERDAY_STR = YESTERDAY.strftime("%Y-%m-%d")
YESTERDAY2_STR = YESTERDAY2.strftime("%Y-%m-%d")


class TestLiveConsumption:
    """Test class for Live consumption feature."""

    ws_client_id = 0
    ws_client_connected = False
    ws_client_responses = {
        # Message 1
        json.dumps({"type": "auth", "access_token": "fake_token"}): [
            False,
            {"type": "auth_ok"},
        ],
        # Message 2
        json.dumps(
            {
                "end_time": f"{YESTERDAY_STR}T00:00:00-04:00",
                "id": 1,
                "period": "day",
                "start_time": f"{YESTERDAY2_STR}T00:00:00-04:00",
                "statistic_ids": ["sensor.hydroqc_home_hourly_consumption"],
                "type": "history/statistics_during_period",
            }
        ): [
            False,
            {
                "result": {
                    "sensor.hydroqc_home_hourly_consumption": [{"sum": 0}, {"sum": 1}]
                }
            },
        ],
        # Message 3
        json.dumps(
            {
                "id": 2,
                "type": "recorder/import_statistics",
                "metadata": {
                    "has_mean": False,
                    "has_sum": True,
                    "name": None,
                    "source": "recorder",
                    "statistic_id": "sensor.hydroqc_home_hourly_consumption",
                    "unit_of_measurement": "kWh",
                },
                "stats": [
                    {
                        "start": f"{YESTERDAY_STR}T00:00:00-04:00",
                        "state": 2.23,
                        "sum": 3.23,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T01:00:00-04:00",
                        "state": 2.22,
                        "sum": 5.45,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T02:00:00-04:00",
                        "state": 2.21,
                        "sum": 7.66,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T03:00:00-04:00",
                        "state": 2.06,
                        "sum": 9.72,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T04:00:00-04:00",
                        "state": 1.36,
                        "sum": 11.08,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T05:00:00-04:00",
                        "state": 1.81,
                        "sum": 12.89,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T06:00:00-04:00",
                        "state": 1.36,
                        "sum": 14.25,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T07:00:00-04:00",
                        "state": 1.79,
                        "sum": 16.04,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T08:00:00-04:00",
                        "state": 2.93,
                        "sum": 18.97,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T09:00:00-04:00",
                        "state": 3.6,
                        "sum": 22.57,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T10:00:00-04:00",
                        "state": 2.36,
                        "sum": 24.93,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T11:00:00-04:00",
                        "state": 3.03,
                        "sum": 27.96,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T12:00:00-04:00",
                        "state": 3.14,
                        "sum": 31.1,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T13:00:00-04:00",
                        "state": 2.6,
                        "sum": 33.7,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T14:00:00-04:00",
                        "state": 2.58,
                        "sum": 36.28,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T15:00:00-04:00",
                        "state": 2.12,
                        "sum": 38.4,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T16:00:00-04:00",
                        "state": 1.7,
                        "sum": 40.1,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T17:00:00-04:00",
                        "state": 2.1,
                        "sum": 42.2,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T18:00:00-04:00",
                        "state": 5.04,
                        "sum": 47.24,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T19:00:00-04:00",
                        "state": 3.33,
                        "sum": 50.57,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T20:00:00-04:00",
                        "state": 3.15,
                        "sum": 53.72,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T21:00:00-04:00",
                        "state": 3.63,
                        "sum": 57.35,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T22:00:00-04:00",
                        "state": 2.69,
                        "sum": 60.04,
                    },
                    {
                        "start": f"{YESTERDAY_STR}T23:00:00-04:00",
                        "state": 2.9,
                        "sum": 62.94,
                    },
                ],
            }
        ): [False, {"success": True}],
        # Message 4
        json.dumps(
            {
                "end_time": f"{TODAY_STR}T00:00:00-04:00",
                "id": 1,
                "period": "day",
                "start_time": f"{YESTERDAY_STR}T00:00:00-04:00",
                "statistic_ids": ["sensor.hydroqc_home_hourly_consumption"],
                "type": "history/statistics_during_period",
            }
        ): [
            False,
            {
                "result": {
                    "sensor.hydroqc_home_hourly_consumption": [
                        {"sum": 60.04},
                        {"sum": 62.94},
                    ]
                }
            },
        ],
        # Message 5
        json.dumps(
            {
                "id": 2,
                "type": "recorder/import_statistics",
                "metadata": {
                    "has_mean": False,
                    "has_sum": True,
                    "name": None,
                    "source": "recorder",
                    "statistic_id": "sensor.hydroqc_home_hourly_consumption",
                    "unit_of_measurement": "kWh",
                },
                "stats": [
                    {
                        "start": f"{TODAY_STR}T00:00:00-04:00",
                        "state": 2.23,
                        "sum": 65.17,
                    },
                    {
                        "start": f"{TODAY_STR}T01:00:00-04:00",
                        "state": 2.22,
                        "sum": 67.39,
                    },
                    {
                        "start": f"{TODAY_STR}T02:00:00-04:00",
                        "state": 2.21,
                        "sum": 69.6,
                    },
                    {
                        "start": f"{TODAY_STR}T03:00:00-04:00",
                        "state": 2.06,
                        "sum": 71.66,
                    },
                    {
                        "start": f"{TODAY_STR}T04:00:00-04:00",
                        "state": 1.36,
                        "sum": 73.02,
                    },
                    {
                        "start": f"{TODAY_STR}T05:00:00-04:00",
                        "state": 1.81,
                        "sum": 74.83,
                    },
                    {
                        "start": f"{TODAY_STR}T06:00:00-04:00",
                        "state": 1.36,
                        "sum": 76.19,
                    },
                    {
                        "start": f"{TODAY_STR}T07:00:00-04:00",
                        "state": 1.79,
                        "sum": 77.98,
                    },
                    {
                        "start": f"{TODAY_STR}T08:00:00-04:00",
                        "state": 2.93,
                        "sum": 80.91000000000001,
                    },
                    {
                        "start": f"{TODAY_STR}T09:00:00-04:00",
                        "state": 3.6,
                        "sum": 84.51,
                    },
                    {
                        "start": f"{TODAY_STR}T10:00:00-04:00",
                        "state": 2.36,
                        "sum": 86.87,
                    },
                    {
                        "start": f"{TODAY_STR}T11:00:00-04:00",
                        "state": 3.03,
                        "sum": 89.9,
                    },
                    {
                        "start": f"{TODAY_STR}T12:00:00-04:00",
                        "state": 3.14,
                        "sum": 93.04,
                    },
                    {
                        "start": f"{TODAY_STR}T13:00:00-04:00",
                        "state": 2.6,
                        "sum": 95.64,
                    },
                    {
                        "start": f"{TODAY_STR}T14:00:00-04:00",
                        "state": 2.58,
                        "sum": 98.22,
                    },
                    {
                        "start": f"{TODAY_STR}T15:00:00-04:00",
                        "state": 2.12,
                        "sum": 100.34,
                    },
                    {
                        "start": f"{TODAY_STR}T16:00:00-04:00",
                        "state": 1.7,
                        "sum": 102.04,
                    },
                    {
                        "start": f"{TODAY_STR}T17:00:00-04:00",
                        "state": 2.1,
                        "sum": 104.14,
                    },
                    {
                        "start": f"{TODAY_STR}T18:00:00-04:00",
                        "state": 5.04,
                        "sum": 109.18,
                    },
                    {
                        "start": f"{TODAY_STR}T19:00:00-04:00",
                        "state": 3.33,
                        "sum": 112.51,
                    },
                    {
                        "start": f"{TODAY_STR}T20:00:00-04:00",
                        "state": 3.15,
                        "sum": 115.66000000000001,
                    },
                    {
                        "start": f"{TODAY_STR}T21:00:00-04:00",
                        "state": 3.63,
                        "sum": 119.29,
                    },
                    {
                        "start": f"{TODAY_STR}T22:00:00-04:00",
                        "state": 2.69,
                        "sum": 121.98,
                    },
                    {
                        "start": f"{TODAY_STR}T23:00:00-04:00",
                        "state": 2.9,
                        "sum": 124.88000000000001,
                    },
                ],
            }
            # Message 6
        ): [False, {"success": True}],
    }

    def _new_ws_client(
        self,
        client: dict[str, int | WebSocketHandler | tuple[str | int]],
        server: WebsocketServer,
    ) -> None:
        """Send first WS message when when a new client is connected to the WS server."""
        server.send_message(client, json.dumps({"type": "auth_required"}))

    def _new_ws_message(
        self,
        client: dict[str, int | WebSocketHandler | tuple[str | int]],
        server: WebsocketServer,
        message: str,
    ) -> None:
        """Send WS responses when a new message is received by the WS server."""
        assert message in self.ws_client_responses
        if self.ws_client_id == 0:
            assert "id" not in json.loads(message)
        else:
            assert json.loads(message)["id"] == self.ws_client_id
        self.ws_client_id += 1
        self.ws_client_responses[message][0] = True
        server.send_message(client, json.dumps(self.ws_client_responses[message][1]))
        if self.ws_client_id == 3:
            self.ws_client_id = 0

    def teardown(self) -> None:
        """Teardown test method."""
        # import ipdb;ipdb.set_trace()
        self.server.shutdown()
        self.thread.join()

    def setup(self) -> None:
        """Set up test method."""
        self.server = WebsocketServer(
            host=WS_SERVER_HOST, port=WS_SERVER_PORT, loglevel=logging.INFO
        )
        self.server.set_fn_new_client(self._new_ws_client)
        self.server.set_fn_message_received(self._new_ws_message)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def test_base_sync_consumption(  # pylint: disable=too-many-locals
        self,
    ) -> None:
        """Test Sync consumption for hydroqc2mqtt."""
        # Prepare MQTT Client
        client = mqtt.Client("hydroqc-test")
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        expected_results = {}
        for root, _, files in os.walk("tests/expected_mqtt_data", topdown=False):
            for filename in files:
                filepath = os.path.join(root, filename)
                key = filepath.replace("tests/expected_mqtt_data/", "")
                with open(filepath, "rb") as fht:
                    expected_results[key] = fht.read().strip()

        def on_connect(
            client: mqtt.Client,
            userdata: dict[str, Any] | None,  # pylint: disable=unused-argument
            flags: dict[str, Any],  # pylint: disable=unused-argument
            rc_: int,  # pylint: disable=unused-argument
        ) -> None:  # pylint: disable=unused-argument
            for topic in expected_results:
                client.subscribe(topic)

        collected_results = {}

        def on_message(
            client: mqtt.Client,  # pylint: disable=unused-argument
            userdata: dict[str, Any] | None,  # pylint: disable=unused-argument
            msg: mqtt.MQTTMessage,
        ) -> None:
            collected_results[msg.topic] = msg.payload

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()  # type: ignore[no-untyped-call]
        os.environ["HQ2M_CONTRACTS_0_SYNC_HOURLY_CONSUMPTION_ENABLED"] = "true"
        os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_WEBSOCKET_URL"] = WS_SERVER_URL
        os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_TOKEN"] = "fake_token"

        # await asyncio.sleep(1)
        time.sleep(1)

        # Prepare http mocking
        with aioresponses(passthrough=[WS_SERVER_URL]) as mres:  # type: ignore[no-untyped-call]
            # LOGIN
            mres.post(
                AUTH_URL,
                payload={
                    "callbacks": [
                        {"input": [{"value": "username"}]},
                        {"input": [{"value": "password"}]},
                    ]
                },
            )

            mres.post(
                AUTH_URL,
                payload={"tokenId": "FAKE_TOKEN"},
            )

            fake_scope = "FAKE_SCOPE"
            fake_oauth2_client_id = "FAKE_OAUTH2_CLIENT_ID"
            fake_redirect_uri = "https://FAKE_REDIRECTURI.com"
            # fake_redirect_uri_enc = urllib.parse.quote(fake_redirect_uri, safe="")
            mres.get(
                SECURITY_URL,
                repeat=True,
                payload={
                    "oauth2": [
                        {
                            "clientId": fake_oauth2_client_id,
                            "redirectUri": fake_redirect_uri,
                            "scope": fake_scope,
                        }
                    ]
                },
            )

            encoded_id_token_data = {"exp": int(time.time()) + 18000}
            encoded_id_token = b".".join(
                (
                    base64.b64encode(b"FAKE_TOKEN"),
                    base64.b64encode(json.dumps(encoded_id_token_data).encode()),
                )
            ).decode()
            access_token_url = SESSION_REFRESH_URL.replace("/silent-refresh", "")
            callback_url = (
                f"{access_token_url}#"
                f"access_token=FAKE_ACCESS_TOKEN&id_token={encoded_id_token}"
            )
            reurl3 = re.compile(r"^" + AUTHORIZE_URL + r"\?client_id=.*$")
            mres.get(reurl3, status=302, headers={"Location": callback_url})

            mres.get(callback_url)

            url5 = LOGIN_URL_6
            mres.get(url5)

            mres.get(
                SECURITY_URL,
                payload={
                    "oauth2": [
                        {
                            "clientId": fake_oauth2_client_id,
                            "redirectUri": fake_redirect_uri,
                            "scope": fake_scope,
                        }
                    ]
                },
            )
            callback_url = (
                f"{SESSION_REFRESH_URL}#"
                f"access_token=FAKE_ACCESS_TOKEN&id_token={encoded_id_token}"
            )
            mres.get(reurl3, status=302, headers={"Location": callback_url})
            mres.get(callback_url)

            # DATA
            # TODO make it relative to this file
            with open("tests/input_http_data/relations.json", "rb") as fht:
                payload_6 = json.load(fht)
            mres.get(RELATION_URL, payload=payload_6)
            # Second time for consumption data sync
            mres.get(RELATION_URL, payload=payload_6)

            url_7 = re.compile(r"^" + CUSTOMER_INFO_URL + r".*$")
            with open("tests/input_http_data/infoCompte.json", "rb") as fht:
                payload_7 = json.load(fht)
            mres.get(url_7, payload=payload_7, repeat=True)

            mres.get(f"{SESSION_URL}?mode=web")

            mres.get(f"{PORTRAIT_URL}?noContrat={CONTRACT_ID}")

            with open(
                "tests/input_http_data/resourceObtenirDonneesPeriodesConsommation.json",
                "rb",
            ) as fht:
                payload_10 = json.load(fht)
            mres.get(PERIOD_DATA_URL, payload=payload_10)

            with open("tests/input_http_data/creditPointeCritique.json", "rb") as fht:
                payload_11 = json.load(fht)
            mres.get(GET_WINTER_CREDIT_API_URL, payload=payload_11)

            mres.get(
                f"{GET_WINTER_CREDIT_API_URL}?noContrat={CONTRACT_ID}",
                payload=payload_11,
            )

            with open(
                "tests/input_http_data/resourceObtenirDonneesConsommationHoraires.json",
                "rb",
            ) as fht:
                payload_12 = json.load(fht)
                payload_12["results"]["dateJour"] = YESTERDAY_STR
            mres.get(
                f"{HOURLY_CONSUMPTION_API_URL}?date={YESTERDAY_STR}", payload=payload_12
            )
            mres.get(
                f"{HOURLY_CONSUMPTION_API_URL}?date={TODAY_STR}", payload=payload_12
            )

            del sys.argv[1:]
            sys.argv.append("--run-once")
            main()

            # Check some data in MQTT
            time.sleep(1)
            for topic, expected_value in expected_results.items():
                assert topic in collected_results
                try:
                    expected_json_value = json.loads(expected_value)
                    if topic.endswith("/config"):
                        expected_json_value["device"]["sw_version"] = VERSION
                    assert json.loads(collected_results[topic]) == expected_json_value
                except json.decoder.JSONDecodeError:
                    assert collected_results[topic].strip() == expected_value.strip()

            assert (
                all(v[0] for v in self.ws_client_responses.values()) is True
            ), "At least one of the expected websocket message is missing."
