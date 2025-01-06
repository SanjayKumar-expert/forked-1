FROM registry.gitlab.com/hydroqc/hydroqc-base-container/3.12:latest AS builder

ARG HYDROQC2MQTT_VERSION

ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HYDROQC2MQTT=${HYDROQC2MQTT_VERSION}

# UV specific configs
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app

WORKDIR /build

# We install the project dependencies first to take advantage of Docker layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Copy the files needed to install the project
COPY setup.cfg pyproject.toml uv.lock /build/
COPY hydroqc2mqtt /build/hydroqc2mqtt

# Install the project in the venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm

COPY --from=builder --chown=nobody:nogroup /app /app
WORKDIR /app
USER nobody:nogroup
ENV PATH="/app/bin:$PATH"
ENV TZ="America/Toronto" \
    MQTT_DISCOVERY_DATA_TOPIC="homeassistant" \
    MQTT_DATA_ROOT_TOPIC="hydroqc" \
    SYNC_FREQUENCY=600

CMD ["hydroqc2mqtt"]
