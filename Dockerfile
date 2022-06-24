FROM debian:testing-20220527-slim

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install --no-install-recommends -y gcc musl-dev python3.10 python3.10-dev python3-venv python3-pip build-essential

WORKDIR /usr/src/app

COPY ./docker/entrypoint.sh .
COPY ./config.sample.yaml /etc/hydroqc2mqtt/config.yaml

COPY setup.cfg setup.py /usr/src/app/
COPY hydroqc2mqtt /usr/src/app/hydroqc2mqtt

RUN ["chmod", "+x", "./entrypoint.sh"]

RUN python3 setup.py install

RUN apt-get clean && rm -rf /tmp/setup /var/lib/apt/lists/* /tmp/* /var/tmp/*

CMD [ "./entrypoint.sh" ]
