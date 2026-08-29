# Chaos Agent

Chaos Agent is a safety-focused controller for injecting controlled incidents into an isolated development web server. The eventual target is a Linux VM running an Apache-hosted static site, while this application runs separately on a dedicated control VM.

Phase 3 adds durable experiment lifecycle state, bounded cleanup controls, leases, audit records, and supervised request handling. The production scenario catalog remains empty until Phase 4, so this phase performs no real fault injection.

## Responsibility boundaries

The project keeps three responsibilities separate:

```text
Chaos Agent   -> injects a predefined, bounded fault
Remedy Agent  -> detects, diagnoses, and repairs the fault
Observer      -> independently evaluates impact and recovery
```

Only the first component belongs to this repository. Automatic expiry and cleanup added in later phases will be emergency safety behavior, not the remedy being tested.

The passive runtime and on-demand preflight remain separate:

```text
validated configuration
        -> passive process
        -> atomic local heartbeat
        -> local-only health result

explicit target configuration
        -> fixed OpenSSH helper operations
        -> target identity and baseline policy
        -> bounded external HTTP observation
        -> sanitized preflight report
```

The long-running process remains passive. Only an explicit `chaos preflight` invocation performs the fixed read-only SSH and HTTP checks. No Phase 2 path changes Apache, resources, files, networking, or target configuration.

## Current capabilities

- Python 3.12+ package managed with `uv`.
- Typer CLI with human-readable and JSON output.
- Typed `CHAOS_` environment configuration.
- Structured JSON or console logs with conservative secret redaction.
- Passive long-running process with `SIGINT` and `SIGTERM` handling.
- Atomic, permission-restricted runtime heartbeat.
- Local agent and storage health checks.
- Non-root, read-only-root container deployment with persistent data.
- Automated Python and container lifecycle tests.
- Strict host-key pinning and root-owned application identity verification.
- Read-only Apache, disk-reserve, memory-reserve, load, and website preflight.
- Durable experiment status, history, cancellation, reconciliation, leases, and cleanup audit records.

## Prerequisites

Local Python development requires:

- Python 3.12 or newer;
- `uv` 0.12 or a compatible newer release; and
- Git.

Container development and deployment additionally require:

- Docker Engine with the Compose plugin, or Docker Desktop; and
- access to the configured container registries and Python package index during the first build.

The deployed container contains Python 3.12.13. Its Python and `uv` build images are pinned by manifest digest in the Dockerfile.

## Local setup

Synchronize the locked runtime and development environment:

```sh
uv sync --all-groups --locked
```

Confirm both supported entry points:

```sh
uv run chaos version
uv run python -m chaos_agent version
```

The deployed data-directory default is `/var/lib/chaos-agent`. For unprivileged local development, select a repository-local ignored directory explicitly:

```sh
export CHAOS_DATA_DIR="$PWD/.chaos-agent-data"
uv run chaos config-check
```

The application does not silently load an environment file. If you create one from [the safe example](config/agent.env.example), load it explicitly through your shell or deployment tooling. Never commit the resulting file.

## CLI commands

### General help

```sh
uv run chaos
uv run chaos --help
```

### Version

```sh
uv run chaos version
uv run chaos version --json
```

Example JSON:

```json
{"version":"0.1.0"}
```

### Configuration validation

```sh
uv run chaos config-check
uv run chaos config-check --json
```

Invalid configuration returns exit code `2`. Validation output reports fields and rules but omits rejected input values.

### Passive runtime

Start the local passive agent in the foreground:

```sh
export CHAOS_DATA_DIR="$PWD/.chaos-agent-data"
export CHAOS_LOG_FORMAT=console
uv run chaos agent
```

Use `Ctrl-C` to request a clean shutdown. The runtime writes `agent-status.json` inside the configured data directory and marks it `stopped` during an orderly exit.

### Local agent health

While the passive runtime is active, use another terminal with the same configuration:

```sh
export CHAOS_DATA_DIR="$PWD/.chaos-agent-data"
uv run chaos health
uv run chaos health --json
```

Healthy output returns exit code `0`. Invalid configuration, unavailable storage, or an invalid runtime heartbeat returns a non-zero status.

### Read-only target preflight

After an operator has provisioned the target according to [the target access guide](ops/target/README.md), supplied the complete target configuration, and independently verified the SSH host fingerprint:

```sh
uv run chaos preflight
uv run chaos preflight --json
```

Preflight checks configuration, the local OpenSSH client, SSH file safety, helper compatibility, target identity, scoped `sudo`, Apache, resource reserves, and finally the externally visible website. Later checks are marked `skip` when a prerequisite fails.

Exit codes are stable:

| Code | Meaning |
| --- | --- |
| `0` | Every required check passed |
| `1` | A verified identity, privilege, target baseline, or website policy refused the target |
| `2` | Configuration or local SSH/CA material is invalid or missing |
| `3` | Transport, protocol, cancellation, or internal execution failed safely |

Neither human nor JSON output contains SSH file contents, raw helper output, response bodies, or complete process arguments.

## Configuration

All runtime configuration comes from environment variables using the `CHAOS_` prefix.

| Variable | Default | Rules and meaning |
| --- | --- | --- |
| `CHAOS_AGENT_ID` | `chaos-agent-dev` | 3–63 lowercase letters, numbers, `_`, or `-`; begins and ends alphanumerically |
| `CHAOS_ENVIRONMENT` | `development` | The current agent accepts only `development` |
| `CHAOS_DATA_DIR` | `/var/lib/chaos-agent` | Absolute path; cannot be a root, home, or SSH-material directory |
| `CHAOS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `CHAOS_LOG_FORMAT` | `json` | `json` or `console` |
| `CHAOS_HEARTBEAT_INTERVAL_SECONDS` | `10` | Integer from 1 through 300 |
| `CHAOS_HEARTBEAT_MAX_AGE_SECONDS` | `30` | Integer from 2 through 900 and at least twice the interval |
| `CHAOS_TARGET_ID` | none | Required UUID assigned to the root-owned development target marker |
| `CHAOS_TARGET_HOST` | none | Required DNS name or IP; no user, port, URI, whitespace, or option syntax |
| `CHAOS_TARGET_PORT` | `22` | Integer from 1 through 65535 |
| `CHAOS_TARGET_USER` | `chaos-agent` | Dedicated conservative Linux username; `root` is forbidden |
| `CHAOS_SSH_PRIVATE_KEY_PATH` | `/run/secrets/chaos-agent/ssh/id_ed25519` | Absolute, regular, non-symlink file with mode `0600` or stricter |
| `CHAOS_SSH_KNOWN_HOSTS_PATH` | `/run/secrets/chaos-agent/ssh/known_hosts` | Absolute, regular, non-symlink file not writable by group or other |
| `CHAOS_SSH_CONNECT_TIMEOUT_SECONDS` | `5` | Integer from 1 through 30 |
| `CHAOS_SSH_COMMAND_TIMEOUT_SECONDS` | `15` | Integer from 2 through 60 and greater than the connect timeout |
| `CHAOS_TARGET_APACHE_SERVICE` | `apache2.service` | `apache2.service` or `httpd.service`; must match the target marker |
| `CHAOS_PREFLIGHT_MIN_ROOT_FREE_MIB` | `1024` | Required minimum root-filesystem free space in MiB |
| `CHAOS_PREFLIGHT_MIN_MEMORY_AVAILABLE_MIB` | `256` | Required minimum available memory in MiB |
| `CHAOS_PREFLIGHT_MAX_LOAD_PER_CPU` | `1.50` | Maximum one-minute load divided by logical CPU count |
| `CHAOS_SITE_HEALTH_URL` | none | Required HTTP(S) URL without credentials or fragment |
| `CHAOS_SITE_EXPECTED_STATUS` | `200` | Expected HTTP status from 100 through 599 |
| `CHAOS_SITE_EXPECTED_CONTENT` | none | Optional printable content marker, 1–128 characters |
| `CHAOS_SITE_TIMEOUT_SECONDS` | `5` | Per-I/O and total website request deadline, at most 30 seconds |
| `CHAOS_SITE_MAX_RESPONSE_BYTES` | `65536` | Maximum decoded response bytes retained for marker checking |
| `CHAOS_SITE_CA_BUNDLE_PATH` | none | Optional absolute, read-only CA bundle; TLS cannot be disabled |

The container uses the displayed defaults. Local development should override `CHAOS_DATA_DIR` to a writable absolute path. Console logging is convenient locally, while JSON remains the deployment default.

The target ID and host are configuration, not authentication. Never put private keys, passwords, tokens, host-key contents, or CA contents in environment variables.

## Logging

Deployed JSON logs contain:

- UTC timestamp;
- log level;
- stable event name;
- sanitized message;
- agent ID when available; and
- sanitized structured fields when supplied.

Redaction covers common password, token, authorization, API-key, and private-key representations. Redaction is defense in depth, not permission to send secrets to logs. Never log complete configuration or environment dictionaries.

Runtime logs go to standard error so the container runtime can collect them. CLI result output goes to standard output.

## Container deployment

### Build and start

The Compose deployment builds the pinned multi-stage image and starts the passive agent:

```sh
docker compose build
docker compose up --detach --wait
```

No inbound port is exposed. Inspect service and health state with:

```sh
docker compose ps
docker compose exec chaos-agent chaos health --json
docker compose logs chaos-agent
```

The service runs with:

- UID and GID `10001`;
- a read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges` enabled;
- no Docker socket mount;
- a small temporary in-memory `/tmp`;
- an `unless-stopped` restart policy; and
- a ten-second stop grace period.

### Configuration overrides

Compose accepts safe operational overrides from the invoking environment:

```sh
export CHAOS_AGENT_ID=chaos-agent-dev
export CHAOS_LOG_LEVEL=DEBUG
docker compose up --detach --wait
```

Do not place secrets in the repository's `.env` file. Target access uses read-only file mounts, not secret-valued environment variables.

### Stop or remove the service

Request a graceful stop:

```sh
docker compose stop --timeout 10
```

Remove the stopped container and network while preserving agent data:

```sh
docker compose down
```

`docker compose down --volumes` also deletes the persistent agent-data volume. Use it only when intentionally discarding local runtime state.

## Persistent data and SSH mount

Compose mounts the named `agent-data` volume at `/var/lib/chaos-agent`. The image initializes this location for UID/GID `10001`, avoiding world-writable permissions. The heartbeat is operational state; Phase 3 will add SQLite experiment history beneath this same persistent root.

The base Compose service starts passively without target configuration or SSH mounts. For an operator-configured deployment, copy `compose.target.yaml.example` outside normal source control or use it directly as a reviewed overlay after creating `secrets/ssh/id_ed25519` and `secrets/ssh/known_hosts`:

```sh
docker compose -f compose.yaml -f compose.target.yaml.example config
docker compose -f compose.yaml -f compose.target.yaml.example up --detach --wait
docker compose -f compose.yaml -f compose.target.yaml.example exec chaos-agent chaos preflight --json
```

The overlay requires target ID, host, and website URL explicitly and mounts the private key and `known_hosts` as two individual read-only files. Docker is instructed not to create missing host paths. Both files remain ignored by Git.

Do not copy a whole home or `.ssh` directory into this project. Never bake SSH material into the image. The container contains an outbound OpenSSH client, but no SSH server, host keys, target credentials, or populated `known_hosts` file.

## Health semantics

`chaos health` means only that:

- the local runtime configuration is valid;
- the local data directory exists and is writable;
- a well-formed heartbeat belongs to the configured agent;
- the passive runtime reports `ready`; and
- its heartbeat timestamp is current.

It does **not** mean that:

- the development web VM is reachable;
- SSH is configured;
- Apache is running;
- the website is available; or
- a future remedy agent is healthy.

Those remote checks belong only to `chaos preflight` and remain separately reported. Website health alone never proves target identity, and preflight health does not change the meaning of the local container health check.

An orderly shutdown marks the heartbeat `stopped`, making local health fail immediately. A crash leaves the previous heartbeat behind, which becomes unhealthy when its maximum age is exceeded.

## Automated checks

Run the Python quality gates:

```sh
uv sync --all-groups --locked
uv run pytest --cov=chaos_agent --cov-report=term-missing
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv build
git diff --check
```

Run Compose syntax validation and the live isolated container lifecycle test:

```sh
docker compose config --quiet
sh -n scripts/container-smoke.sh
./scripts/container-smoke.sh
```

The smoke script builds a temporary tagged image and creates uniquely named temporary containers and volumes. It cleans up those containers and volumes when it exits. It verifies non-root identity, runtime restrictions, health and stale-heartbeat behavior, persistent data, image exclusions, and graceful stop.

Neither the Python suite nor the container smoke test contacts the development web VM or injects a fault.

Real-target validation is optional, read-only, and deliberately guarded. Review all configuration and SSH material, verify the server fingerprint through an independent channel, then invoke:

```sh
export CHAOS_REAL_TARGET_ACK=I_ACKNOWLEDGE_READ_ONLY_DEV_PREFLIGHT
export CHAOS_SSH_PRIVATE_KEY_PATH="$PWD/secrets/ssh/id_ed25519"
export CHAOS_SSH_KNOWN_HOSTS_PATH="$PWD/secrets/ssh/known_hosts"
./scripts/real-target-preflight.sh --json
```

The guard requires the acknowledgement, target UUID, host, site URL, private key, and `known_hosts`. A hostname by itself can never authorize a target. Running this procedure is an explicit operator action; it is not part of automated tests.

## Troubleshooting

### Configuration is invalid

Run:

```sh
uv run chaos config-check --json
```

Check the reported field against the configuration table. Common causes include a relative data path, unsupported log value, invalid agent ID, or a heartbeat maximum age less than twice its interval. The command intentionally omits the rejected value.

### Data directory is missing or unwritable

For local development, set an absolute path owned by your user:

```sh
export CHAOS_DATA_DIR="$PWD/.chaos-agent-data"
```

Do not solve permission errors with world-writable modes or by running the agent as root. For Compose, prefer the provided named volume. If deployment storage is bind-mounted later, make its ownership match UID/GID `10001` before starting the service.

### Health reports a missing heartbeat

The health command does not start the runtime. Start `chaos agent` locally or `docker compose up --detach --wait` for the container deployment, using the same agent ID and data directory as the health command.

### Health reports a stale, mismatched, or stopped heartbeat

- `stale` means the runtime stopped updating within `CHAOS_HEARTBEAT_MAX_AGE_SECONDS`.
- `different agent` means the heartbeat's agent ID does not match current configuration.
- `runtime is not ready` commonly means the previous process shut down cleanly and marked itself stopped.

Inspect runtime logs and configuration. Do not manually edit the heartbeat as an operational fix. Restart the passive agent after resolving the underlying configuration or storage issue.

### Container fails to start or become healthy

Inspect:

```sh
docker compose ps
docker compose logs chaos-agent
docker compose config
```

Confirm Docker is running, the image registries are reachable for the initial build, `secrets/ssh/` exists, and the persistent volume is writable by UID/GID `10001`. The service exposes no port, so the absence of a browser endpoint is expected.

### Container cannot stop cleanly

Use `docker compose stop --timeout 10` and inspect the logs for `agent.shutdown_requested` and `agent.stopped`. Do not use a forced kill during normal operation; later phases will rely on the same graceful window for experiment cleanup and reconciliation.

### Preflight configuration or SSH files are refused

Run `chaos preflight --json` and inspect the stable category. Confirm all three required target values are set together. Check that the key and `known_hosts` are regular non-empty files, not symlinks; the private key has no group or other permission bits; and neither file is writable by group or other. The agent intentionally does not repair modes or create host-key entries.

### Host-key or authentication failure

Do not bypass strict checking. Re-verify the target fingerprint independently before changing `known_hosts`. Confirm the dedicated public key is installed with the forced dispatcher restrictions. Authentication fallback, passwords, default keys, SSH agents, and interactive prompts are disabled.

### Target identity, helper, or privilege refusal

Compare the configured UUID and Apache service with the root-owned marker through the target console. Validate installed ownership and modes with the target guide, then validate the narrow sudoers fragment with `visudo -cf`. Do not broaden sudo permissions or replace the dispatcher with a shell to make preflight pass.

### Apache, resource, or website refusal

Preflight only reports the failed baseline. It does not start Apache, remove files, terminate processes, change memory, follow redirects, or repair the website. Resolve the underlying development-environment condition through normal operator procedures and run preflight again.

## Phase 2 limitations

Phase 2 intentionally does not provide:

- experiment state, SQLite history, expiry, cleanup, or reconciliation;
- Apache-stop, CPU-pressure, or disk-pressure scenarios;
- API, dashboard, observer, or remedy-agent integration; or
- arbitrary shell, subprocess, or AI-generated command execution.

The CLI is not yet an incident launcher. Target access is read-only and selects only the fixed helper operations.

## Phase 3 handoff

Phase 3 adds experiment lifecycle, persistence, automatic expiry, cleanup, reconciliation, and continuous observations while preserving the Phase 2 target identity and transport boundaries. It must not turn the helper or CLI into a generic remote shell.

Phase 2 completion does not authorize a scenario to run without its later scenario-specific safety design and implementation.

## Project planning

- [Project roadmap](ROADMAP.md)
- [Phase 1 specification](specs/phase-01-foundation.md)
- [Phase 2 specification](specs/phase-02-secure-target-access.md)
- [Target access operations guide](ops/target/README.md)
- [Project implementation guidance](AGENTS.md)
