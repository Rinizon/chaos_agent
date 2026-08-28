# Chaos Agent

Chaos Agent is a safety-focused controller for injecting controlled incidents into an isolated development web server. The eventual target is a Linux VM running an Apache-hosted static site, while this application runs separately on a dedicated control VM.

Phase 1 is deliberately passive. It provides a validated Python application, local runtime heartbeat, health reporting, safe logs, and hardened container deployment. It cannot connect to another machine or cause an incident yet.

## Responsibility boundaries

The project keeps three responsibilities separate:

```text
Chaos Agent   -> injects a predefined, bounded fault
Remedy Agent  -> detects, diagnoses, and repairs the fault
Observer      -> independently evaluates impact and recovery
```

Only the first component belongs to this repository. Automatic expiry and cleanup added in later phases will be emergency safety behavior, not the remedy being tested.

The current Phase 1 runtime does only this:

```text
validated configuration
        -> passive process
        -> atomic local heartbeat
        -> local-only health result
```

It performs no SSH, HTTP, Apache, subprocess, shell, or chaos operation.

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

## Configuration

All runtime configuration comes from environment variables using the `CHAOS_` prefix.

| Variable | Default | Rules and meaning |
| --- | --- | --- |
| `CHAOS_AGENT_ID` | `chaos-agent-dev` | 3–63 lowercase letters, numbers, `_`, or `-`; begins and ends alphanumerically |
| `CHAOS_ENVIRONMENT` | `development` | Phase 1 accepts only `development` |
| `CHAOS_DATA_DIR` | `/var/lib/chaos-agent` | Absolute path; cannot be a root, home, or SSH-material directory |
| `CHAOS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `CHAOS_LOG_FORMAT` | `json` | `json` or `console` |
| `CHAOS_HEARTBEAT_INTERVAL_SECONDS` | `10` | Integer from 1 through 300 |
| `CHAOS_HEARTBEAT_MAX_AGE_SECONDS` | `30` | Integer from 2 through 900 and at least twice the interval |

The container uses the displayed defaults. Local development should override `CHAOS_DATA_DIR` to a writable absolute path. Console logging is convenient locally, while JSON remains the deployment default.

Configuration is non-secret in Phase 1. Do not use these variables to carry SSH keys, passwords, tokens, or other credentials.

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

Do not place secrets in the repository's `.env` file. Phase 1 needs none.

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

Compose also mounts the dedicated repository directory `secrets/ssh/` read-only at `/run/secrets/chaos-agent/ssh`. Phase 1 does not read it. Its contents are ignored by Git, except for the empty `.gitkeep` placeholder.

Do not copy a whole home directory or `.ssh` directory into this project. Phase 2 will define individual SSH identity and `known_hosts` files, their permissions, and the deployment procedure. Never bake SSH material into the image.

## Health semantics

`chaos health` means only that:

- the Phase 1 configuration is valid;
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

Those checks belong to later phases and remain separately reported.

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

## Phase 1 limitations

Phase 1 intentionally does not provide:

- SSH connectivity or target credentials;
- target allowlisting or identity verification;
- remote helper or `sudoers` configuration;
- website or Apache checks;
- experiment state, SQLite history, expiry, cleanup, or reconciliation;
- Apache-stop, CPU-pressure, or disk-pressure scenarios;
- API, dashboard, observer, or remedy-agent integration; or
- arbitrary shell, subprocess, or AI-generated command execution.

The CLI is not yet an incident launcher. Its passive runtime exists so later work can extend one supervised process model safely.

## Phase 2 handoff

Phase 2 adds secure target access and read-only preflight behavior. It must preserve these Phase 1 boundaries:

- add target and SSH settings without changing current environment semantics unexpectedly;
- add `preflight` through application services rather than Typer business logic;
- keep transport adapters outside the domain layer;
- retain the fixed non-root container identity and read-only-root posture;
- mount only a dedicated SSH identity and `known_hosts` read-only;
- retain structured sanitization while adding target and operation identifiers;
- refuse unknown or mismatched targets; and
- expose only fixed, allowlisted remote operations—never a general remote shell.

Phase 2 owns the SSH implementation choice, target-identity mechanism, remote helper design, and restricted `sudo` contract. It does not authorize chaos injection.

## Project planning

- [Project roadmap](ROADMAP.md)
- [Phase 1 specification](specs/phase-01-foundation.md)
- [Project implementation guidance](AGENTS.md)
