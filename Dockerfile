FROM registry.gitlab.com/hydroqc/hydroqc-base-container

WORKDIR /usr/src/app

COPY ./docker/entrypoint.sh .
COPY ./config.sample.yaml /etc/hydroqc2mqtt/config.yaml

COPY setup.cfg setup.py /usr/src/app/
COPY hydroqc2mqtt /usr/src/app/hydroqc2mqtt

RUN ["chmod", "+x", "./entrypoint.sh"]

RUN python3 setup.py install

CMD [ "./entrypoint.sh" ]
