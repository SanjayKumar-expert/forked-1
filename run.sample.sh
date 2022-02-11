
MQTT_USERNAME=username \
MQTT_PASSWORD=password \
MQTT_HOST=192.168.1.1 \
MQTT_PORT=1883 \
MQTT_DISCOVERY_DATA_TOPIC="homeassistant" \
MQTT_DATA_ROOT_TOPIC="hydroqc" \
H2M_CONTRACTS_0_USERNAME="email0@email.com" \
H2M_CONTRACTS_0_PASSWORD="mypassword0" \
H2M_CONTRACTS_1_USERNAME="email1@email.com" \
H2M_CONTRACTS_1_PASSWORD="mypassword1" \
CONFIG_YAML=config.yaml \
env/bin/hydroqc2mqtt
