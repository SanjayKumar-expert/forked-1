FROM registry.gitlab.com/hydroqc/hydroqc-base-container

WORKDIR /usr/src/app

COPY setup.cfg setup.py /usr/src/app/
COPY hydroqc2mqtt /usr/src/app/hydroqc2mqtt

RUN python3 setup.py install
ENV TZ="America/Toronto" \
    MQTT_DISCOVERY_DATA_TOPIC="homeassistant" \
    MQTT_DATA_ROOT_TOPIC="hydroqc" \
    SYNC_FREQUENCY=600
    
CMD [ "/usr/local/bin/hydroqc2mqtt" ]
