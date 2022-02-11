FROM python:3.9-slim-bullseye

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y gcc musl-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install -r requirements.txt --force-reinstall --no-cache-dir

COPY ./docker/entrypoint.sh .
RUN mkdir /etc/hydroqc2mqtt/
COPY ./config.sample.yaml /etc/hydroqc2mqtt/config.yaml

COPY . .

RUN ["chmod", "+x", "./entrypoint.sh"]

RUN python setup.py install

CMD [ "./entrypoint.sh" ]
