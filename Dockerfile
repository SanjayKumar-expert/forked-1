FROM python:3.9-slim-bullseye

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y gcc musl-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install -r requirements.txt --force-reinstall --no-cache-dir

COPY ./docker/entrypoint.sh .
COPY ./config.sample.yaml /etc/hydroqc2mqtt/config.yaml

COPY . .

RUN ["chmod", "+x", "./entrypoint.sh"]

RUN python setup.py install

RUN apt-get clean && rm -rf /tmp/setup /var/lib/apt/lists/* /tmp/* /var/tmp/*

CMD [ "./entrypoint.sh" ]
