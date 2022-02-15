
MQTT_USERNAME='username' \ # Leave empty if no auth is needed
MQTT_PASSWORD='password' \ # Leave empty if no auth is needed
MQTT_HOST='192.168.1.1' \
MQTT_PORT='1883' \
MQTT_DISCOVERY_DATA_TOPIC='homeassistant' \
MQTT_DATA_ROOT_TOPIC='hydroqc' \
CONFIG_YAML='config.yaml' \
env/bin/hydroqc2mqtt
