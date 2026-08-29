#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_dir=$(CDPATH= cd -- "${script_dir}/.." && pwd)
smoke_suffix="$$"
image_name="chaos-agent:phase-1-smoke"
container_name="chaos-agent-smoke-${smoke_suffix}"
volume_name="chaos-agent-smoke-data-${smoke_suffix}"

cleanup() {
    docker rm --force "${container_name}" >/dev/null 2>&1 || true
    docker volume rm --force "${volume_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker build --tag "${image_name}" "${repository_dir}"
docker volume create "${volume_name}" >/dev/null

docker run --rm --entrypoint /bin/sh "${image_name}" -c \
    'ssh -V >/dev/null 2>&1 && test ! -x /usr/sbin/sshd && test ! -e /root/.ssh && test ! -e /etc/ssh/ssh_known_hosts && ! find /etc/ssh -name "ssh_host_*" -print -quit | grep -q .'

set +e
unconfigured_output=$(docker run --rm "${image_name}" preflight --json 2>/dev/null)
unconfigured_status=$?
set -e
test "${unconfigured_status}" = "2"
printf '%s\n' "${unconfigured_output}" | grep -Fq '"category":"configuration_invalid"'

start_container() {
    docker run --detach \
        --name "${container_name}" \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
        --cap-drop ALL \
        --security-opt no-new-privileges \
        --health-interval 1s \
        --health-timeout 2s \
        --health-retries 2 \
        --health-start-period 1s \
        --mount "type=volume,source=${volume_name},target=/var/lib/chaos-agent" \
        "${image_name}" >/dev/null
}

wait_until_healthy() {
    attempts=0
    while [ "${attempts}" -lt 30 ]; do
        status=$(docker inspect --format '{{.State.Health.Status}}' "${container_name}")
        if [ "${status}" = "healthy" ]; then
            return 0
        fi
        if [ "${status}" = "unhealthy" ]; then
            docker logs "${container_name}"
            return 1
        fi
        attempts=$((attempts + 1))
        sleep 1
    done
    docker logs "${container_name}"
    return 1
}

wait_until_unhealthy() {
    attempts=0
    while [ "${attempts}" -lt 8 ]; do
        status=$(docker inspect --format '{{.State.Health.Status}}' "${container_name}")
        if [ "${status}" = "unhealthy" ]; then
            return 0
        fi
        attempts=$((attempts + 1))
        sleep 1
    done
    docker logs "${container_name}"
    return 1
}

start_container
wait_until_healthy

test "$(docker exec "${container_name}" id -u)" = "10001"
test "$(docker exec "${container_name}" id -g)" = "10001"
test "$(docker inspect --format '{{.HostConfig.Privileged}}' "${container_name}")" = "false"
test "$(docker inspect --format '{{json .HostConfig.CapDrop}}' "${container_name}")" = '["ALL"]'
test "$(docker inspect --format '{{json .HostConfig.SecurityOpt}}' "${container_name}")" = '["no-new-privileges"]'

mount_destinations=$(docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "${container_name}")
if printf '%s\n' "${mount_destinations}" | grep -Fqx '/var/run/docker.sock'; then
    echo "Docker socket must not be mounted" >&2
    exit 1
fi

docker exec "${container_name}" test -f /var/lib/chaos-agent/agent-status.json
docker exec "${container_name}" touch /var/lib/chaos-agent/persistence-marker
docker exec "${container_name}" python -c \
    'import json; from pathlib import Path; path = Path("/var/lib/chaos-agent/agent-status.json"); heartbeat = json.loads(path.read_text()); heartbeat["last_heartbeat_at"] = "2000-01-01T00:00:00Z"; path.write_text(json.dumps(heartbeat))'
wait_until_unhealthy

docker stop --time 10 "${container_name}" >/dev/null
test "$(docker inspect --format '{{.State.ExitCode}}' "${container_name}")" = "0"
docker rm "${container_name}" >/dev/null

start_container
wait_until_healthy
docker exec "${container_name}" test -f /var/lib/chaos-agent/persistence-marker

docker run --rm --entrypoint /bin/sh "${image_name}" -c \
    'test ! -e /opt/chaos-agent/.git && test ! -e /opt/chaos-agent/tests && test ! -e /opt/chaos-agent/.env && test ! -e /opt/chaos-agent/ops'

docker stop --time 10 "${container_name}" >/dev/null
test "$(docker inspect --format '{{.State.ExitCode}}' "${container_name}")" = "0"

echo "Container smoke checks passed."
