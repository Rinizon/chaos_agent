# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv

FROM ${PYTHON_IMAGE} AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/chaos-agent/.venv

WORKDIR /opt/chaos-agent

COPY --from=uv /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime

ARG AGENT_UID=10001
ARG AGENT_GID=10001

ENV PATH=/opt/chaos-agent/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHAOS_AGENT_ID=chaos-agent-dev \
    CHAOS_ENVIRONMENT=development \
    CHAOS_DATA_DIR=/var/lib/chaos-agent \
    CHAOS_LOG_LEVEL=INFO \
    CHAOS_LOG_FORMAT=json \
    CHAOS_HEARTBEAT_INTERVAL_SECONDS=10 \
    CHAOS_HEARTBEAT_MAX_AGE_SECONDS=30

RUN apt-get update \
    && apt-get install --yes --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${AGENT_GID}" chaos-agent \
    && useradd --uid "${AGENT_UID}" --gid "${AGENT_GID}" \
        --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin chaos-agent \
    && install -d -o "${AGENT_UID}" -g "${AGENT_GID}" -m 0700 \
        /var/lib/chaos-agent /run/secrets/chaos-agent/ssh

WORKDIR /opt/chaos-agent
COPY --from=builder /opt/chaos-agent/.venv /opt/chaos-agent/.venv

USER ${AGENT_UID}:${AGENT_GID}

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["chaos", "health", "--json"]

ENTRYPOINT ["chaos"]
CMD ["agent"]
