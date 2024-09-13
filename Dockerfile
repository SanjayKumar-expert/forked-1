FROM registry.gitlab.com/hydroqc/hydroqc-base-container/3.12:latest@sha256:35b47cbac42b1ecab8081a04dca64c5820ec9aff41db68314a4851ea462faec5 as build-image

ARG HYDROQC2MQTT_VERSION

WORKDIR /usr/src/app

COPY setup.cfg pyproject.toml /usr/src/app/
COPY hydroqc2mqtt /usr/src/app/hydroqc2mqtt

# See https://github.com/pypa/setuptools/issues/3269
ENV DEB_PYTHON_INSTALL_LAYOUT=deb_system

ENV DISTRIBUTION_NAME=HYDROQC2MQTT
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HYDROQC2MQTT=${HYDROQC2MQTT_VERSION}
ENV UV_NO_CACHE=true

# Uncomment when using dev builds of hydroqc-api-wrapper in setup.cfg
# ENV UV_EXTRA_INDEX_URL=https://gitlab.com/api/v4/projects/32908244/packages/pypi/simple

RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv

RUN uv pip install --upgrade pip uv && \
    uv pip install --upgrade setuptools_scm && \
    uv pip install . \
    uv pip install msgpack ujson

FROM python:3.12-slim-bookworm@sha256:15bad989b293be1dd5eb26a87ecacadaee1559f98e29f02bf6d00c8d86129f39

COPY --from=build-image /opt/venv/pyvenv.cfg /opt/venv/pyvenv.cfg
COPY --from=build-image /opt/venv/lib /opt/venv/lib
COPY --from=build-image /opt/venv/bin /opt/venv/bin

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
