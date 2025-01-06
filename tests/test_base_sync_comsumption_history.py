"""Base tests for hydroqc2mqtt."""

import asyncio
import base64
import json
import os
import re
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from aioresponses import aioresponses
from hydroqc.hydro_api.consts import (
    AUTH_URL,
    AUTHORIZE_URL,
    AZB2C_POLICY,
    CONTRACT_LIST_URL,
    CONTRACT_SUMMARY_URL,
    CUSTOMER_INFO_URL,
    PORTRAIT_URL,
    RELATION_URL,
    SESSION_URL,
    TOKEN_URL,
)

from hydroqc2mqtt.__main__ import _parse_cmd
from hydroqc2mqtt.daemon import Hydroqc2Mqtt
from hydroqc2mqtt.hourly_consump_handler import HAEnergyStatType

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


@pytest.mark.asyncio(loop_scope="class")
class TestHistoryConsumption:
    """Test class for Live consumption feature."""

    def teardown_method(self) -> None:
        """Teardown test method."""

    def setup_method(self) -> None:
        """Set up test method."""

    @pytest_asyncio.fixture(loop_scope="class", scope="class")
    async def daemon(self) -> AsyncGenerator[Hydroqc2Mqtt]:
        """Fixture to keep the webuser instance through all tests."""
        del sys.argv[1:]
        sys.argv.append("--run-once")
        cmd_args = _parse_cmd()
        daemon = Hydroqc2Mqtt(
            mqtt_host=cmd_args.mqtt_host,
            mqtt_port=cmd_args.mqtt_port,
            mqtt_username=cmd_args.mqtt_username,
            mqtt_password=cmd_args.mqtt_password,
            mqtt_transport="tcp",
            mqtt_ssl_enabled=False,
            mqtt_websocket_path="",
            mqtt_discovery_root_topic=cmd_args.mqtt_discovery_root_topic,
            mqtt_data_root_topic=cmd_args.mqtt_data_root_topic,
            config_file=cmd_args.config,
            run_once=cmd_args.run_once,
            log_level=cmd_args.log_level,
            http_log_level=cmd_args.http_log_level,
            hq_username=cmd_args.hq_username,
            hq_password=cmd_args.hq_password,
            hq_name=cmd_args.hq_name,
            hq_customer_id=cmd_args.hq_customer_id,
            hq_account_id=cmd_args.hq_account_id,
            hq_contract_id=cmd_args.hq_contract_id,
        )
        yield daemon
        if daemon.contracts and daemon.contracts[0]._webuser:
            await daemon.contracts[0]._webuser.close_session()

    async def test_base_sync_consumption(  # pylint: disable=too-many-locals
        self,
        daemon: Hydroqc2Mqtt,
    ) -> None:
        """Test Sync consumption for hydroqc2mqtt."""
        os.environ["HQ2M_CONTRACTS_0_SYNC_HOURLY_CONSUMPTION_ENABLED"] = "true"
        os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_WEBSOCKET_URL"] = WS_SERVER_URL
        os.environ["HQ2M_CONTRACTS_0_HOME_ASSISTANT_TOKEN"] = "fake_token"

        await asyncio.sleep(1)

        # Prepare http mocking
        with aioresponses(passthrough=[WS_SERVER_URL]) as mres:
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

            # Run Daemon manually
            del sys.argv[1:]
            sys.argv.append("--run-once")

            daemon.must_run = True
            # Get contract
            async with AsyncExitStack() as stack:
                await daemon._mqtt_connect(stack)
                await daemon._init_main_loop(stack)

                contract = daemon.contracts[0]
                await contract.get_contract()
                await contract.add_entities()

                # Mocking the send_consumption_statistics method
                self.send_consumption_statistics_nb_called = 0

                # Mock get_hourly_energy
                async def mock_get_hourly_energy(
                    start_date: str,
                    end_date: str,
                    raw_output: bool = False,  # pylint: disable=unused-argument
                ) -> list[list[str]]:
                    data: list[list[str]] = []
                    data = []
                    for hour in range(0, 24):
                        value = f"{hour},00"
                        data.append(
                            [
                                "0000000000",
                                f"{start_date} {hour:02}:00:00",
                                value,
                                "R",
                                "0",
                                "R",
                            ]
                        )
                    for hour in range(0, 24):
                        value = f"{hour},00"
                        data.append(
                            [
                                "0000000000",
                                f"{end_date} {hour:02}:00:00",
                                value,
                                "R",
                                "0",
                                "R",
                            ]
                        )
                    data.reverse()
                    header = [
                        "Contrat",
                        "Date et heure",
                        "kWh",
                        "Code de consommation",
                        "Température moyenne (°C)",
                        "Code de température",
                    ]
                    data.insert(0, header)
                    return data

                assert contract._webuser is not None
                contract._webuser.customers[0].accounts[0].contracts[
                    0
                ].get_hourly_energy = mock_get_hourly_energy  # type:ignore

                # Connecting to the contract
                # await contract.init_session()
                @pytest.mark.asyncio(loop_scope="class")
                async def mock_send_consptn_stats(
                    stats: list[HAEnergyStatType],
                    consumption_type: str,  # pylint: disable=unused-argument
                    data_date: date,  # pylint: disable=unused-argument
                ) -> None:
                    self.send_consumption_statistics_nb_called += 1
                    # We want to ensure that all data sent to WS are correct
                    assert sum(s["state"] for s in stats) == sum(range(0, 24)) * 2

                contract._hch.send_consumption_statistics = (  # type:ignore
                    mock_send_consptn_stats
                )

                # Starting importing data
                await contract._hch.get_hourly_consumption_history()

                # We check if we called method send_consumption_statistics_nb_called
                # only one time
                assert self.send_consumption_statistics_nb_called == 1
