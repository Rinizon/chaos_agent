#!/bin/sh
set -eu

required_ack="I_ACKNOWLEDGE_READ_ONLY_DEV_PREFLIGHT"
if [ "${CHAOS_REAL_TARGET_ACK:-}" != "${required_ack}" ]; then
    echo "Refusing real-target preflight: explicit acknowledgement is required." >&2
    exit 2
fi

if [ -z "${CHAOS_TARGET_ID:-}" ] \
    || [ -z "${CHAOS_TARGET_HOST:-}" ] \
    || [ -z "${CHAOS_SITE_HEALTH_URL:-}" ]; then
    echo "Refusing real-target preflight: target UUID, host, and site URL are required." >&2
    exit 2
fi

key_path="${CHAOS_SSH_PRIVATE_KEY_PATH:-/run/secrets/chaos-agent/ssh/id_ed25519}"
hosts_path="${CHAOS_SSH_KNOWN_HOSTS_PATH:-/run/secrets/chaos-agent/ssh/known_hosts}"
if [ ! -f "${key_path}" ] || [ ! -f "${hosts_path}" ]; then
    echo "Refusing real-target preflight: reviewed SSH files are required." >&2
    exit 2
fi

exec uv run chaos preflight "$@"
