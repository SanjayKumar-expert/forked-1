#!/bin/sh
set -e

# Config
if [ -z "$CONFIG_YAML" ]
then
    export CONFIG_YAML="config.docker.yaml"
fi

/usr/local/bin/hydroqc2mqtt
