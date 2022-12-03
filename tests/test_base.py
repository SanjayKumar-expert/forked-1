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
    CONTRACT_LIST_URL,
    CONTRACT_SUMMARY_URL,
    CUSTOMER_INFO_URL,
    GET_WINTER_CREDIT_API_URL,
    LOGIN_URL_6,
    PERIOD_DATA_URL,
    PORTRAIT_URL,
    RELATION_URL,
    SECURITY_URL,
    SESSION_REFRESH_URL,
    SESSION_URL,
)

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
    client.loop_start()

    time.sleep(1)

    # Prepare http mocking
    with aioresponses() as mres:  # type: ignore[no-untyped-call]
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
        mres.get(GET_WINTER_CREDIT_API_URL, payload=payload_13)

        mres.get(
            f"{GET_WINTER_CREDIT_API_URL}?noContrat={CONTRACT_ID}", payload=payload_13
        )

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
