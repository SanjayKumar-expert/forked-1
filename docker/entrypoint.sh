#!/bin/sh
set -e

# Config
if [ -z "$CONFIG_YAML" ]
then
    export CONFIG_YAML="config.docker.yaml"
fi

env/bin/hydroqc2mqtt
