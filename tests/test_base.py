"""Base tests for hydroqc2mqtt."""

import base64
import json
import os
import re
import sys
import time
from typing import Any

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
    IS_HYDRO_PORTAL_UP_URL,
    OPEN_DATA_PEAK_URL,
    OUTAGES,
    PERIOD_DATA_URL,
    PORTRAIT_URL,
    RELATION_URL,
    SESSION_URL,
    TOKEN_URL,
)
from paho.mqtt.client import CallbackAPIVersion  # type:ignore[attr-defined]
from paho.mqtt.client import ConnectFlags
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from hydroqc2mqtt.__main__ import main
from hydroqc2mqtt.__version__ import VERSION

CONTRACT_ID = os.environ["HQ2M_CONTRACTS_0_CONTRACT"]
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ["MQTT_PORT"])
MQTT_DISCOVERY_ROOT_TOPIC = os.environ.get(
    "MQTT_DISCOVERY_ROOT_TOPIC", os.environ.get("ROOT_TOPIC", "homeassistant")
)
MQTT_DATA_ROOT_TOPIC = os.environ.get("MQTT_DATA_ROOT_TOPIC", "homeassistant")


def test_base() -> None:  # pylint: disable=too-many-locals
    """Base test for hydroqc2mqtt."""
    # Prepare MQTT Client
    client = mqtt.Client(
        client_id="hydroqc-test", callback_api_version=CallbackAPIVersion.VERSION2
    )
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

    time.sleep(1)

    # Prepare http mocking
    with aioresponses() as mres:
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
            authorize_url_reg, body=f'''"csrf":"{csrf_token}","transId":"{transid}"'''
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

        with open(
            "tests/input_http_data/calculerSommaireContractuel.json", "rb"
        ) as fht:
            payload_7 = json.load(fht)
        mres.get(CONTRACT_SUMMARY_URL, payload=payload_7)

        with open("tests/input_http_data/contrats.json", "rb") as fht:
            payload_8 = json.load(fht)

        mres.post(CONTRACT_LIST_URL, payload=payload_8)

        url_9 = re.compile(r"^" + CUSTOMER_INFO_URL + r".*$")
        with open("tests/input_http_data/infoCompte.json", "rb") as fht:
            payload_9 = json.load(fht)
        mres.get(url_9, payload=payload_9, repeat=True)

        mres.get(f"{SESSION_URL}?mode=web")

        mres.get(f"{PORTRAIT_URL}?noContrat={CONTRACT_ID}")

        with open(
            "tests/input_http_data/resourceObtenirDonneesPeriodesConsommation.json",
            "rb",
        ) as fht:
            payload_12 = json.load(fht)
        mres.get(PERIOD_DATA_URL, payload=payload_12)

        with open("tests/input_http_data/creditPointeCritique.json", "rb") as fht:
            payload_13 = json.load(fht)
        mres.get(GET_CPC_API_URL, payload=payload_13)

        mres.get(f"{GET_CPC_API_URL}?noContrat={CONTRACT_ID}", payload=payload_13)

        with open("tests/input_http_data/outages.json", "rb") as fht:
            payload_14 = json.load(fht)
        mres.get(OUTAGES + "6666666666", payload=payload_14)

        with open("tests/input_http_data/pointeshivernales.json", "rb") as fht:
            payload_15 = json.load(fht)
        mres.get(OPEN_DATA_PEAK_URL, payload=payload_15)

        # Run main loop once
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
