#!/bin/sh
set -e

# Config
if [ -z "$CONFIG_YAML" ]
then
    export CONFIG_YAML="/etc/hydroqc2mqtt/config.yaml"
fi

if [ -z "$MQTT_DISCOVERY_DATA_TOPIC" ]
then
    export MQTT_DISCOVERY_DATA_TOPIC="homeassistant"
fi

if [ -z "$MQTT_DATA_ROOT_TOPIC" ]
then
    export MQTT_DATA_ROOT_TOPIC="hydroqc"
fi

if [ -z "$TZ" ]
then
    export TZ="America/Toronto"
fi

/usr/local/bin/hydroqc2mqtt
