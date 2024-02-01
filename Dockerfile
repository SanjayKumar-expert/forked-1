FROM registry.gitlab.com/hydroqc/hydroqc-base-container/3.11:latest@sha256:0f3e011c82c334b14282cb46e40cb87c676de8bb501600500d37855e548244f8 as build-image

ARG HYDROQC2MQTT_VERSION

WORKDIR /usr/src/app

COPY setup.cfg pyproject.toml /usr/src/app/
COPY hydroqc2mqtt /usr/src/app/hydroqc2mqtt

# See https://github.com/pypa/setuptools/issues/3269
ENV DEB_PYTHON_INSTALL_LAYOUT=deb_system

ENV DISTRIBUTION_NAME=HYDROQC2MQTT
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HYDROQC2MQTT=${HYDROQC2MQTT_VERSION}

RUN python3.11 -m venv /opt/venv

RUN --mount=type=tmpfs,target=/root/.cargo \
    curl https://sh.rustup.rs -sSf | \
    RUSTUP_INIT_SKIP_PATH_CHECK=yes sh -s -- -y && \
    export PATH="/root/.cargo/bin:${PATH}"

RUN if [ `dpkg --print-architecture` = "armhf" ]; then \
       printf "[global]\nextra-index-url=https://www.piwheels.org/simple\n" > /etc/pip.conf ; \
    fi

RUN --mount=type=tmpfs,target=/root/.cargo \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install --upgrade setuptools_scm && \
    pip config set global.extra-index-url https://gitlab.com/api/v4/projects/32908244/packages/pypi/simple && \
    pip install --no-cache-dir .

RUN . /opt/venv/bin/activate && \
    pip install --no-cache-dir msgpack ujson


FROM python:3.11-slim-bookworm@sha256:53d6284a40eae6b625f22870f5faba6c54f2a28db9027408f4dee111f1e885a2
COPY --from=build-image /opt/venv /opt/venv
COPY --from=build-image /usr/src/app/hydroqc2mqtt /usr/src/app/hydroqc2mqtt
COPY --from=build-image /opt/venv/bin/hydroqc2mqtt /opt/venv/bin/hydroqc2mqtt

RUN \
    adduser hq2m \
        --uid 568 \
        --group \
        --system \
        --disabled-password \
        --no-create-home

USER hq2m

ENV PATH="/opt/venv/bin:$PATH"
ENV TZ="America/Toronto" \
    MQTT_DISCOVERY_DATA_TOPIC="homeassistant" \
    MQTT_DATA_ROOT_TOPIC="hydroqc" \
    SYNC_FREQUENCY=600

CMD [ "/opt/venv/bin/hydroqc2mqtt" ]
