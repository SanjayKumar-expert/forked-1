"""Base tests for hydroqc2mqtt."""

import asyncio
import base64
import copy
import json

# import logging
import os
import re
import sys

# import threading
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import paho.mqtt.client as mqtt
from aioresponses import aioresponses
from hydroqc.hydro_api.consts import (
    AUTH_URL,
    AUTHORIZE_URL,
    AZB2C_POLICY,
    CONTRACT_LIST_URL,
    CONTRACT_SUMMARY_URL,
    CUSTOMER_INFO_URL,
    GET_CPC_API_URL,
    HOURLY_CONSUMPTION_API_URL,
    IS_HYDRO_PORTAL_UP_URL,
    OPEN_DATA_PEAK_URL,
    OUTAGES,
    PERIOD_DATA_URL,
    PORTRAIT_URL,
    RELATION_URL,
    SESSION_URL,
    TOKEN_URL,
)
from hydroqc.utils import EST_TIMEZONE
from packaging import version
from paho.mqtt.client import CallbackAPIVersion  # type:ignore[attr-defined]
from paho.mqtt.client import ConnectFlags
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

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

TODAY = datetime.today()
YESTERDAY = TODAY - timedelta(days=1)
YESTERDAY2 = TODAY - timedelta(days=2)
TODAY_MINUS_3 = TODAY - timedelta(days=3)
TODAY_MINUS_4 = TODAY - timedelta(days=4)
TODAY_MINUS_5 = TODAY - timedelta(days=5)
TODAY_MINUS_6 = TODAY - timedelta(days=6)
TODAY_MINUS_7 = TODAY - timedelta(days=7)
TODAY_STR = TODAY.strftime("%Y-%m-%d")
YESTERDAY_STR = YESTERDAY.strftime("%Y-%m-%d")
YESTERDAY2_STR = YESTERDAY2.strftime("%Y-%m-%d")
TODAY_MINUS_3_STR = TODAY_MINUS_3.strftime("%Y-%m-%d")
TODAY_MINUS_4_STR = TODAY_MINUS_4.strftime("%Y-%m-%d")
TODAY_MINUS_5_STR = TODAY_MINUS_5.strftime("%Y-%m-%d")
TODAY_MINUS_6_STR = TODAY_MINUS_6.strftime("%Y-%m-%d")
TODAY_MINUS_7_STR = TODAY_MINUS_7.strftime("%Y-%m-%d")


async def check_data_in_hass() -> None:
    """Check stats data in hass."""
    query_id = 1
    ws_server_url = os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_WEBSOCKET_URL"]
    hass_token = os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_TOKEN"]
    async with aiohttp.ClientSession() as client:
        websocket = await client.ws_connect(ws_server_url)
        response = await websocket.receive_json()
        ha_version = response["ha_version"]
        # Auth
        await websocket.send_json({"type": "auth", "access_token": hass_token})
        response = await websocket.receive_json()
        # Get data from yesterday
        data_date = datetime.today().astimezone(EST_TIMEZONE)
        data_start_date_str = (data_date - timedelta(days=1)).isoformat()
        data_end_date_str = data_date.isoformat()

        websocket_call_type = (
            "history/statistics_during_period"
            if version.parse(ha_version) < version.parse("2022.10.0")
            else "recorder/statistics_during_period"
        )
        await websocket.send_json(
            {
                "end_time": data_end_date_str,
                "id": query_id,
                "period": "day",
                "start_time": data_start_date_str,
                "statistic_ids": ["sensor.hydroqc_home_total_hourly_consumption"],
                "type": websocket_call_type,
            }
        )
        response = await websocket.receive_json()
        assert (
            response["result"]["sensor.hydroqc_home_total_hourly_consumption"][0]["sum"]
            == 433.58
        )


class TestLiveConsumption:
    """Test class for Live consumption feature."""

    def test_base_sync_consumption(  # pylint: disable=too-many-locals,too-many-statements
        self,
    ) -> None:
        """Test Sync consumption for hydroqc2mqtt."""
        # Prepare MQTT Client
        client = mqtt.Client(
            client_id="hydroqc-test",
            callback_api_version=CallbackAPIVersion.VERSION2,
        )
        if MQTT_USERNAME and MQTT_PASSWORD:
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
            flags: ConnectFlags,  # pylint: disable=unused-argument
            rc_: ReasonCode,  # pylint: disable=unused-argument
            properties: Properties,  # pylint: disable=unused-argument
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

        client.on_connect = on_connect  # type:ignore[assignment]
        client.on_message = on_message
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        os.environ["HQ2M_CONTRACTS_0_SYNC_HOURLY_CONSUMPTION_ENABLED"] = "true"
        # os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_WEBSOCKET_URL"] = WS_SERVER_URL
        # os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_TOKEN"] = "fake_token"

        # await asyncio.sleep(1)
        time.sleep(1)

        # Prepare http mocking
        ws_server_url = os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_WEBSOCKET_URL"]
        with aioresponses(passthrough=[ws_server_url]) as mres:
            # STATUS
            mres.get(
                IS_HYDRO_PORTAL_UP_URL,
                status=200,
            )

            # LOGIN
            csrf_token = "FAKECSRFTOKEN"
            transid = "FAKETRANSID"
            code = "FAKE_CODE"
            authorize_url_reg = re.compile(AUTHORIZE_URL + r"\?.*")
            mres.get(
                authorize_url_reg,
                body=f'''"csrf":"{csrf_token}","transId":"{transid}"''',
            )

            mres.post(
                AUTH_URL + "?tx=FAKETRANSID&p=" + AZB2C_POLICY,
                payload={
                    "status": "200",
                },
            )

            url = (
                "https://connexion.solutions.hydroquebec.com/32bf9b91-0a36-4385-b231-d9a8fa3b05ab"
                + "/B2C_1A_PRD_signup_signin/api/CombinedSigninAndSignup/"
                + "confirmed?rememberMe=false&csrf_token="
                + csrf_token
                + "&tx="
                + transid
                + "&p="
                + AZB2C_POLICY
            )
            mres.get(url, status=302, headers={"Location": f"code={code}"})

            encoded_id_token_data = {
                "sub": "fake_webuser_id",
                "exp": int(time.time()) + 18000,
            }
            encoded_id_token = b".".join(
                (
                    base64.b64encode(b"FAKE_TOKEN"),
                    base64.b64encode(json.dumps(encoded_id_token_data).encode()),
                )
            ).decode()
            response_payload = {
                "access_token": encoded_id_token,
                "id_token": encoded_id_token,
                "token_type": "Bearer",
                "not_before": 1702929095,
                "expires_in": 900,
                "expires_on": 1702929995,
                "resource": "09b0ae72-6db8-4ecc-a1be-041b67afc1cd",
                "id_token_expires_in": 900,
                "profile_info": "FAKE",
                "scope": "https://connexionhq.onmicrosoft.com/hq-clientele/Espace.Client openid",
                "refresh_token": encoded_id_token,
                "refresh_token_expires_in": 86400,
            }
            mres.post(TOKEN_URL, payload=response_payload)
            mres.post(TOKEN_URL, payload=response_payload)
            mres.post(TOKEN_URL, payload=response_payload)

            # DATA
            # TODO make it relative to this file
            with open("tests/input_http_data/relations.json", "rb") as fht:
                payload_6 = json.load(fht)
            mres.get(RELATION_URL, payload=payload_6)
            # Second time for consumption data sync
            mres.get(RELATION_URL, payload=payload_6)

            with open(
                "tests/input_http_data/calculerSommaireContractuel.json", "rb"
            ) as fht:
                payload_7 = json.load(fht)
                print(CONTRACT_SUMMARY_URL)
            mres.get(CONTRACT_SUMMARY_URL, payload=payload_7)

            with open("tests/input_http_data/contrats.json", "rb") as fht:
                payload_8 = json.load(fht)

            mres.post(CONTRACT_LIST_URL, payload=payload_8)

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
            mres.get(GET_CPC_API_URL, payload=payload_11)

            mres.get(
                f"{GET_CPC_API_URL}?noContrat={CONTRACT_ID}",
                payload=payload_11,
            )

            with open(
                "tests/input_http_data/resourceObtenirDonneesConsommationHoraires.json",
                "rb",
            ) as fht:
                payload_12 = json.load(fht)
                payload_12["results"]["dateJour"] = TODAY_STR
                payload_12_1 = copy.copy(payload_12)
                payload_12_1["results"]["dateJour"] = YESTERDAY_STR
                payload_12_2 = copy.copy(payload_12)
                payload_12_2["results"]["dateJour"] = YESTERDAY2_STR
                payload_12_3 = copy.copy(payload_12)
                payload_12_3["results"]["dateJour"] = TODAY_MINUS_3_STR
                payload_12_4 = copy.copy(payload_12)
                payload_12_4["results"]["dateJour"] = TODAY_MINUS_4_STR
                payload_12_5 = copy.copy(payload_12)
                payload_12_5["results"]["dateJour"] = TODAY_MINUS_5_STR
                payload_12_6 = copy.copy(payload_12)
                payload_12_6["results"]["dateJour"] = TODAY_MINUS_6_STR
                payload_12_7 = copy.copy(payload_12)
                payload_12_7["results"]["dateJour"] = TODAY_MINUS_7_STR

            url_pattern = re.compile(HOURLY_CONSUMPTION_API_URL + r"\?date=.*")
            mres.get(url_pattern, payload=payload_12_7)
            mres.get(url_pattern, payload=payload_12_6)
            mres.get(url_pattern, payload=payload_12_5)
            mres.get(url_pattern, payload=payload_12_4)
            mres.get(url_pattern, payload=payload_12_3)
            mres.get(url_pattern, payload=payload_12_2)
            mres.get(url_pattern, payload=payload_12_1)
            mres.get(url_pattern, payload=payload_12)

            with open("tests/input_http_data/outages.json", "rb") as fht:
                payload_14 = json.load(fht)
            mres.get(OUTAGES + "6666666666", payload=payload_14)

            with open("tests/input_http_data/pointeshivernales.json", "rb") as fht:
                payload_15 = json.load(fht)
            mres.get(OPEN_DATA_PEAK_URL, payload=payload_15)

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

            asyncio.run(check_data_in_hass())
