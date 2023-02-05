FROM debian:testing-slim as base-image

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        python3.10 \
        python3.10-venv \
        python3-pip \
        curl \
        && \
    apt-get clean



FROM base-image as build-image

ARG HYDROQC2MQTT_VERSION

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        python3.10-dev \
        libffi-dev \
        gcc \
        build-essential \
        libssl-dev \
        cargo \
        && \
    apt-get clean
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    update-alternatives --set python3 /usr/bin/python3.10
WORKDIR /usr/src/app

COPY setup.cfg pyproject.toml /usr/src/app/
COPY hydroqc2mqtt /usr/src/app/hydroqc2mqtt

# See https://github.com/pypa/setuptools/issues/3269
ENV DEB_PYTHON_INSTALL_LAYOUT=deb_system

ENV DISTRIBUTION_NAME=HYDROQC2MQTT
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HYDROQC2MQTT=${HYDROQC2MQTT_VERSION}

RUN python3 -m venv /opt/venv

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
    pip install --no-cache-dir .

RUN . /opt/venv/bin/activate && \
    pip install --no-cache-dir msgpack ujson



FROM base-image
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    update-alternatives --set python3 /usr/bin/python3.10
COPY --from=build-image /opt/venv /opt/venv
COPY --from=build-image /usr/src/app/hydroqc2mqtt /usr/src/app/hydroqc2mqtt
COPY --from=build-image /opt/venv/bin/hydroqc2mqtt /opt/venv/bin/hydroqc2mqtt

ENV PATH="/opt/venv/bin:$PATH"
ENV TZ="America/Toronto" \
    MQTT_DISCOVERY_DATA_TOPIC="homeassistant" \
    MQTT_DATA_ROOT_TOPIC="hydroqc" \
    SYNC_FREQUENCY=600

CMD [ "/opt/venv/bin/hydroqc2mqtt" ]