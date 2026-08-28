# Phase 1 Specification: Project Foundation

## Status

In progress

## Implementation history

### 2026-08-28: Step 1 completed

Delivered the package and tooling scaffold with an installable `src/`-layout package, Typer CLI, module entry point, locked runtime and development dependencies, initial architectural package boundaries, quality-tool configuration, ignore rules, and CLI tests.

Evidence:

- `uv sync --all-groups --locked` completed using Python 3.12.13.
- Pytest passed 5 tests with 90% branch-aware coverage.
- Ruff formatting and lint checks passed.
- Strict mypy checks passed for `src/chaos_agent`.
- `chaos version`, `chaos version --json`, and `python -m chaos_agent version` returned version `0.1.0`.
- Source distribution and wheel builds completed successfully.
- `git diff --check` passed.

### 2026-08-28: Step 2 completed

Delivered typed Pydantic settings loaded from `CHAOS_` environment variables, cross-field timing validation, unsafe data-path rejection, safe human and JSON `config-check` output, structured JSON and console logging, stable event names, recursive field sanitization, free-text secret redaction, and a non-secret example environment file.

Evidence:

- `uv sync --all-groups --locked` completed using the updated dependency lock.
- Pytest passed 29 tests with 95% branch-aware coverage.
- Valid human and JSON configuration checks returned success.
- Invalid configuration returned exit code 2 and omitted a supplied secret value.
- Ruff formatting and lint checks passed.
- Strict mypy checks passed for `src/chaos_agent`.
- Source distribution and wheel builds completed successfully.
- `git diff --check` passed.

### 2026-08-28: Step 3 completed

Delivered a passive long-running agent process, versioned heartbeat model, restrictive atomic file persistence, injected clock and storage seams, signal-aware shutdown, local storage and heartbeat evaluation, and human and JSON `agent` and `health` CLI behavior. Health is explicitly limited to the local agent runtime and does not claim target or website readiness.

Evidence:

- `uv sync --all-groups --locked` completed from the committed lock.
- Pytest passed 47 tests with 92% branch-aware coverage.
- Deterministic tests covered heartbeat updates, missing and malformed state, stale and future timestamps, agent mismatch, stopped state, unwritable storage, and write failures.
- A process-level smoke test delivered `SIGTERM`, observed a clean exit, and verified the final heartbeat was marked `stopped`.
- Ruff formatting and lint checks passed.
- Strict mypy checks passed for `src/chaos_agent`.
- Source distribution and wheel builds completed successfully.
- `git diff --check` passed.

### 2026-08-28: Step 4 completed

Delivered a digest-pinned multi-stage container image, fixed non-root runtime identity, passive default command, local-agent health check, read-only-root Compose deployment, persistent data volume, dedicated read-only future SSH mount, dropped capabilities, no-new-privileges policy, finite stop grace period, restart policy, build-context exclusions, and repeatable container lifecycle smoke automation.

Evidence:

- The image built from the repository using pinned Python 3.12.13 and uv 0.12.7 manifests.
- The smoke automation verified UID/GID 10001, read-only root operation, dropped capabilities, no privilege escalation, absence of a Docker socket mount, persistent data across recreation, excluded sensitive/development artifacts, and clean bounded shutdown.
- Docker reported the container healthy with a current heartbeat and unhealthy after the heartbeat was deliberately made stale.
- The actual Compose service reached healthy state and verified its non-root identity, read-only root filesystem, init process, `unless-stopped` restart policy, read-only SSH-material bind mount, and zero exit code after a ten-second graceful stop window.
- Compose configuration and smoke-script shell syntax validation passed.
- Pytest passed 47 tests with 91% branch-aware coverage.
- Ruff formatting, Ruff lint, strict mypy, locked dependency synchronization, package builds, and `git diff --check` passed.

## 1. Purpose and measurable outcome

Phase 1 establishes a maintainable, typed, tested, and container-first Python foundation for the chaos agent. It must prove that the project can be developed locally and deployed as a safe, non-root container without implementing SSH access, persistence models, or any disruptive scenario.

The measurable outcome is a passive agent runtime and Typer CLI that:

- install and run on Python 3.12 or newer;
- load and validate non-secret configuration;
- emit structured, sanitized logs;
- report local agent health in human-readable or JSON form;
- run in a hardened container as a non-root user;
- shut down cleanly when the container receives a termination signal; and
- pass the documented test, lint, format, and type-check commands.

Phase 1 is complete only when every acceptance criterion in this specification has supporting evidence.

## 2. Scope

### 2.1 In scope

- A `src/`-layout Python package named `chaos_agent`.
- A Typer CLI installed as the `chaos` command.
- A passive long-running `chaos agent` process suitable as the container entry point.
- Non-disruptive `chaos version`, `chaos config-check`, and `chaos health` commands.
- Pydantic-based settings loaded from environment variables.
- Human-readable output by default and JSON output where specified.
- Structured application logging with secret-aware sanitization.
- A local heartbeat/status artifact used by the container health check.
- Pytest unit and container smoke tests.
- Ruff formatting and linting.
- Mypy type checking.
- A production-oriented Dockerfile.
- A Compose file for local deployment on the future chaos-agent VM.
- Persistent application-data storage and read-only SSH-material mount points.
- Basic project documentation and safe example configuration.

### 2.2 Out of scope

- Connecting to any target over SSH.
- Accepting or executing remote commands.
- Target allowlisting or target-identity verification.
- Apache, CPU, disk, memory, or network chaos.
- Experiment models, lifecycle state, expiry, cleanup, or reconciliation.
- SQLAlchemy tables, SQLite schemas, or migrations.
- Website health checks.
- FastAPI, HTTP endpoints, authentication, or a dashboard.
- Remedy-agent behavior.
- Autonomous or model-generated actions.

Phase 1 must not include placeholder functions that accept arbitrary shell commands. Future transport interfaces begin in Phase 2.

## 3. Decisions fixed by this specification

### 3.1 Python and project metadata

- Support Python `>=3.12,<4`.
- Use `pyproject.toml` as the source of package, dependency, build, and tool configuration.
- Use a standard PEP 517 build backend and produce an installable wheel.
- Use `uv` for the documented local dependency and lock-file workflow.
- Commit the generated dependency lock file for repeatable local and container builds.
- Keep runtime dependencies separate from development dependencies.

### 3.2 Runtime dependencies

Phase 1 runtime dependencies are limited to:

- Typer for the CLI;
- Pydantic and Pydantic Settings for configuration; and
- a structured logging library only if the standard library cannot meet the agreed logging contract cleanly.

SQLAlchemy and HTTPX may be declared only when the phase that first uses them is implemented. Avoid speculative dependencies.

### 3.3 Development tools

- Pytest for tests.
- Ruff for formatting and linting.
- Mypy for static type checking.
- Coverage reporting through pytest coverage integration.

All tools must be runnable through documented repository commands. Tool configuration belongs in `pyproject.toml` unless a tool requires a separate file.

### 3.4 Package boundaries

Use the following initial structure:

```text
chaos_agent/
├── AGENTS.md
├── ROADMAP.md
├── README.md
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── uv.lock
├── .dockerignore
├── .gitignore
├── config/
│   └── agent.env.example
├── specs/
│   └── phase-01-foundation.md
├── src/
│   └── chaos_agent/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── logging.py
│       ├── runtime.py
│       ├── health.py
│       ├── domain/
│       │   └── __init__.py
│       ├── application/
│       │   └── __init__.py
│       └── adapters/
│           └── __init__.py
└── tests/
    ├── unit/
    └── smoke/
```

Empty architectural packages are permitted only when they communicate a boundary that Phase 2 or Phase 3 will immediately use. Do not add speculative class hierarchies.

The intended dependency direction is:

```text
CLI and adapters -> application -> domain
```

Domain code must not import Typer, container details, or infrastructure adapters. Phase 1 contains little domain behavior, so simple modules are preferable to premature abstractions.

## 4. User and operator workflows

### 4.1 Local developer setup

A developer can:

1. install the supported Python and `uv`;
2. create or synchronize the environment from committed metadata;
3. run the CLI without setting production credentials;
4. run all automated checks through documented commands; and
5. build and smoke-test the container.

The README must provide copyable commands and explain any host prerequisites.

### 4.2 Inspect the version

`chaos version` prints the installed application version and exits successfully. A JSON option returns a stable object suitable for automation.

Minimum JSON shape:

```json
{
  "version": "0.1.0"
}
```

The version must have one authoritative source and must not be duplicated manually across Python files.

### 4.3 Validate configuration

`chaos config-check` loads and validates settings without starting the runtime. It reports success or actionable validation errors.

- Human-readable output is the default.
- `--json` returns a stable object.
- The command must never print secret values.
- Invalid configuration returns a non-zero exit status.
- Configuration validation must not create or modify files except where explicitly required to confirm the configured data directory is usable. Prefer a non-mutating check when practical.

### 4.4 Run the passive agent

`chaos agent` starts a passive process that performs no remote or disruptive work. It:

- validates configuration before reporting readiness;
- creates the configured data directory when safely permitted;
- writes a small heartbeat/status document atomically at a configured interval;
- logs startup, readiness, degraded state, and shutdown;
- handles `SIGTERM` and `SIGINT` cleanly;
- stops within the container's configured grace period; and
- removes or marks its heartbeat stale during orderly shutdown so health cannot remain falsely green.

The passive runtime exists to establish the deployment and process-supervision contract. Phase 3 will extend it into the experiment worker rather than creating a separate competing runtime.

### 4.5 Check local agent health

`chaos health` checks only the local agent and its required local resources. It must not imply that the future target VM or website is healthy.

When invoked inside the running container, it checks at least:

- settings can be loaded;
- the data directory exists and is usable;
- the runtime heartbeat exists and is recent enough; and
- the heartbeat belongs to the configured agent identity.

The command supports `--json` and returns:

- exit `0` for healthy;
- non-zero for unhealthy or invalid configuration.

Minimum JSON shape:

```json
{
  "status": "healthy",
  "agent_id": "chaos-agent-dev",
  "checks": [
    {
      "name": "runtime_heartbeat",
      "status": "pass",
      "message": "heartbeat is current"
    }
  ]
}
```

Do not include hostnames, filesystem paths, environment values, or other potentially sensitive details unless they are explicitly safe and necessary.

## 5. Configuration contract

### 5.1 Source and precedence

Use Pydantic Settings with environment variables as the runtime configuration source. All variables use the `CHAOS_` prefix.

An example environment file may be provided for local development, but the application must not silently load secrets from an untracked path. Compose may explicitly reference a developer-created environment file.

Phase 1 settings:

| Environment variable | Type | Default | Rules |
| --- | --- | --- | --- |
| `CHAOS_AGENT_ID` | string | `chaos-agent-dev` | Non-empty, conservative character set and length |
| `CHAOS_ENVIRONMENT` | enum | `development` | Phase 1 supports `development` only |
| `CHAOS_DATA_DIR` | absolute path | `/var/lib/chaos-agent` in container | Must not be `/`, a home directory, or an SSH-material path |
| `CHAOS_LOG_LEVEL` | enum | `INFO` | Standard supported levels only |
| `CHAOS_LOG_FORMAT` | enum | `json` in container | `json` or `console` |
| `CHAOS_HEARTBEAT_INTERVAL_SECONDS` | integer | `10` | Bounded to a safe documented range |
| `CHAOS_HEARTBEAT_MAX_AGE_SECONDS` | integer | `30` | Must exceed the heartbeat interval with tolerance |

Local development defaults may differ from container defaults only when the difference is explicit in documentation or Compose configuration.

### 5.2 Secrets

Phase 1 requires no operational secrets. Reserve no environment variables for passwords, private-key contents, or tokens.

The Compose file must establish read-only mount locations for a future SSH private key and `known_hosts`, but example files must not contain real key material or host fingerprints. Phase 2 will define the exact SSH settings.

### 5.3 Validation

- Reject unknown values for enums.
- Reject relative data paths in deployed configuration.
- Reject unsafe or overly broad data-directory paths.
- Validate cross-field heartbeat timing.
- Present validation failures without dumping the full environment or settings object.

## 6. Logging and diagnostics

### 6.1 Logging contract

Application logs must include:

- UTC timestamp;
- log level;
- stable event name;
- sanitized message; and
- agent ID when configuration is available.

JSON is the deployed default. Console formatting may be used for local development.

Do not log:

- complete environment dictionaries;
- command-line environment assignments;
- private keys, tokens, passwords, or authorization headers;
- raw exception objects if they contain settings or environment values; or
- entire configuration objects.

### 6.2 Stable events

Define stable event names for at least:

- agent starting;
- agent ready;
- heartbeat write failure;
- agent degraded;
- shutdown requested; and
- agent stopped.

Tests should assert event fields, not decorative rendered strings.

### 6.3 Heartbeat/status artifact

The runtime heartbeat is operational state, not an audit record or experiment database. It must:

- be written inside the configured data directory;
- use an atomic replace operation;
- contain a schema version, agent ID, process start time, last heartbeat time, and runtime status;
- contain no secrets;
- tolerate a reader observing it while updates occur; and
- be replaceable by the persistent runtime model in Phase 3.

## 7. Container and deployment design

### 7.1 Dockerfile

The Dockerfile must:

- use a maintained Python 3.12 slim base image pinned to a sufficiently reproducible reference;
- use a multi-stage build when it materially reduces runtime tooling or image size;
- install dependencies from committed project metadata and lock data;
- copy only required runtime artifacts into the final image;
- create a dedicated non-root user and group with a stable numeric UID/GID;
- set an explicit working directory;
- use exec-form `ENTRYPOINT` and `CMD`;
- start the passive runtime by default;
- include a health check invoking `chaos health --json`;
- avoid package caches and build tools in the final stage where practical; and
- contain no SSH private keys, environment files, test caches, Git metadata, or local databases.

Do not use `latest` image tags in documented deployment examples.

### 7.2 Runtime restrictions

The Compose service must:

- run as the image's non-root user;
- set `no-new-privileges`;
- drop all Linux capabilities unless a documented Phase 1 requirement proves one is necessary;
- avoid privileged mode;
- avoid host PID, IPC, and network namespace sharing;
- avoid mounting the Docker socket;
- mount application data at `/var/lib/chaos-agent`;
- mount future SSH material under `/run/secrets/chaos-agent/ssh` as read-only;
- use a read-only root filesystem where compatible, with explicit writable storage and `tmpfs` for temporary files;
- define a finite stop grace period; and
- use a restart policy appropriate for a long-running control-plane service.

The Phase 1 container does not require inbound network ports.

### 7.3 Storage

- Persist the application data directory through a named volume or explicit deployment path.
- Do not persist caches inside the application-data volume.
- Document ownership requirements for bind-mounted storage.
- Keep the future SQLite location beneath the application-data directory, but do not create a database in Phase 1.

### 7.4 Build context

`.dockerignore` must exclude at least:

- `.git`;
- virtual environments and Python caches;
- test and coverage caches;
- local environment files;
- SSH keys and SSH directories;
- databases and runtime data;
- editor metadata; and
- unrelated local build artifacts.

## 8. Security and safety requirements

- Phase 1 must have no code path that connects to another host.
- The package must not expose a generic subprocess or shell-execution service.
- Container startup must not require root.
- Container health must mean local runtime readiness only.
- Sample configuration must use non-sensitive placeholders.
- Examples must not encourage mounting an entire home or `.ssh` directory.
- SSH mount examples must name individual future files or a dedicated minimal directory and remain read-only.
- Logs, CLI errors, test snapshots, and health output must not expose sensitive environment values.
- The data directory validator must reject dangerously broad locations.
- Generated runtime files must use restrictive, documented permissions.
- Dependencies must come from declared project metadata and the committed lock file.

## 9. Failure modes and required behavior

| Failure | Required behavior |
| --- | --- |
| Invalid configuration | Refuse startup, emit a concise sanitized error, and exit non-zero |
| Data directory cannot be created or written | Refuse readiness and exit or become explicitly unhealthy |
| Heartbeat write fails after readiness | Log the failure, mark the runtime degraded when possible, and make health fail |
| Heartbeat is missing or stale | `chaos health` exits non-zero and reports the failed check |
| Heartbeat belongs to another agent ID | Health fails without exposing unrelated heartbeat contents |
| Runtime receives `SIGTERM` | Stop promptly, record shutdown state when possible, and exit cleanly |
| Runtime crashes | Container health becomes unhealthy and restart policy may restart it |
| JSON output requested during an error | Return valid JSON on stdout and keep diagnostics controlled |
| Unexpected exception | Return non-zero, emit a sanitized error event, and do not dump settings or environment values |

The runtime must never claim healthy merely because its process exists.

## 10. Ordered implementation steps

Each step is an independently verifiable Git change. Follow `AGENTS.md`: inspect status before work, test the step, commit only its files, and leave the tree clean before the next prompt.

### Step 1: Package and tooling scaffold

Deliver:

- `pyproject.toml`, build metadata, runtime and development dependency groups;
- committed `uv.lock`;
- `src/chaos_agent` package and `python -m chaos_agent` wiring;
- Typer `chaos version` command;
- Ruff, mypy, and pytest configuration;
- `.gitignore`; and
- first unit and CLI tests.

Verify:

- environment synchronization succeeds;
- wheel build succeeds;
- `chaos version` works through the installed entry point and module entry point;
- tests, Ruff, and mypy pass.

### Step 2: Configuration and sanitized logging

Deliver:

- typed Phase 1 settings and validators;
- environment-variable loading with the `CHAOS_` prefix;
- `chaos config-check` with human and JSON output;
- structured JSON and console logging;
- stable event fields and sanitization helpers;
- safe example environment file; and
- unit tests for defaults, unsafe paths, timing constraints, invalid values, and redaction.

Verify:

- valid configuration passes;
- invalid configuration fails with a non-zero status;
- tests demonstrate that representative secret-looking values are absent from outputs and logs;
- all automated checks pass.

### Step 3: Passive runtime and local health

Deliver:

- passive runtime loop;
- atomic heartbeat/status writer;
- signal handling;
- `chaos agent` and `chaos health` commands;
- human-readable and JSON health results;
- injected clock and filesystem seams where needed for deterministic tests; and
- tests for current, stale, missing, mismatched, malformed, and unwritable heartbeat cases.

Verify:

- the runtime reaches readiness;
- heartbeat changes over time;
- health succeeds only for a current matching heartbeat;
- `SIGTERM` produces a clean bounded shutdown;
- all automated checks pass.

### Step 4: Container image and Compose deployment

Deliver:

- hardened Dockerfile;
- `.dockerignore`;
- Compose service with persistent data, read-only future SSH mounts, capability restrictions, health check, and restart behavior;
- container-specific safe defaults; and
- smoke-test automation or documented commands.

Verify:

- image builds from a clean checkout;
- container runs as non-root;
- container reaches healthy state;
- container has no Docker socket and no privileged mode;
- mounted data survives container recreation;
- graceful stop completes within the configured grace period;
- image inspection does not reveal environment files, SSH keys, Git metadata, or local runtime data.

### Step 5: Documentation and Phase 1 acceptance

Deliver:

- README covering architecture, local setup, commands, configuration, container deployment, health semantics, storage, and current limitations;
- documented automated-check command set;
- troubleshooting for invalid configuration, permissions, unhealthy heartbeat, and container startup;
- documented Phase 2 handoff assumptions; and
- updated acceptance checklist and evidence in this specification.

Verify:

- a clean-environment walkthrough follows the README successfully;
- all automated and container checks pass;
- no Phase 2 behavior has leaked into the implementation;
- repository status is clean after the final Phase 1 commit.

## 11. Test plan

### 11.1 Unit tests

Cover at minimum:

- configuration defaults and overrides;
- every settings validation boundary;
- heartbeat cross-field constraints;
- safe and rejected data-directory paths;
- log and error sanitization;
- atomic heartbeat serialization and replacement;
- health evaluation for every documented state;
- graceful shutdown behavior using deterministic synchronization rather than arbitrary sleeps; and
- version retrieval from installed package metadata.

### 11.2 CLI tests

Use Typer's test support or an equivalent black-box invocation to cover:

- help output;
- version output;
- config-check success and failure;
- health success and failure;
- valid JSON output for successful and failed commands;
- stable exit-status behavior; and
- absence of secrets in stdout and stderr.

### 11.3 Container smoke tests

Verify:

- image build;
- non-root identity;
- default command startup;
- healthy transition;
- persisted heartbeat storage;
- read-only root-filesystem compatibility;
- termination behavior; and
- absence of forbidden mounts and privileges in Compose configuration.

Container smoke tests must not require or contact the development web VM.

### 11.4 Quality gates

The required Phase 1 quality gates are:

- all Pytest tests pass;
- Ruff formatting check passes;
- Ruff lint passes;
- mypy passes for `src/chaos_agent`;
- wheel build passes;
- container build and smoke test pass; and
- `git diff --check` passes.

Coverage should be reported from the beginning. Set a meaningful threshold only after the initial executable modules exist; do not add empty or meaningless tests merely to satisfy a percentage.

## 12. Acceptance criteria and completion evidence

Update each item from `[ ]` to `[x]` only after recording concrete evidence in the Phase 1 implementation history or pull request.

### Package and CLI

- [x] Python package installs successfully on Python 3.12 or newer.
- [x] A wheel builds successfully from committed metadata and lock data.
- [x] `chaos version` and `python -m chaos_agent version` return the same version.
- [x] CLI help is usable and contains no disruptive commands.

### Configuration and logging

- [x] Valid Phase 1 settings load from documented environment variables.
- [x] Unsafe paths, invalid enum values, and invalid heartbeat timing are rejected.
- [x] `chaos config-check` supports human and JSON output with stable exit statuses.
- [x] Deployed logs are structured JSON with UTC timestamps and stable event names.
- [x] Tests demonstrate that secrets and full environment contents are not exposed.

### Runtime and health

- [x] `chaos agent` runs passively and performs no network or disruptive action.
- [x] Heartbeat updates are atomic and contain no secrets.
- [x] `chaos health` distinguishes healthy, stale, missing, malformed, and mismatched state.
- [x] Graceful shutdown succeeds within the documented time limit.
- [x] A crashed or stopped runtime cannot remain falsely healthy.

### Container

- [x] Container image builds from a clean checkout.
- [x] Runtime process uses a non-root UID/GID.
- [x] Compose drops capabilities, forbids privilege escalation, and mounts no Docker socket.
- [x] Application data persists across container recreation.
- [x] Future SSH material mount points are read-only and contain no repository credentials.
- [x] Container reaches healthy status and becomes unhealthy when the runtime heartbeat is stale.
- [x] Container stops cleanly within its grace period.

### Quality and documentation

- [ ] Pytest, Ruff, mypy, wheel-build, and container-smoke quality gates pass.
- [ ] README setup and deployment instructions work from a clean environment.
- [ ] Phase 1 limitations and Phase 2 handoff assumptions are documented.
- [ ] Repository contains no keys, tokens, environment secrets, databases, or runtime data.
- [ ] Working tree is clean after the Phase 1 completion commit.

## 13. Documentation requirements

The Phase 1 README must explain:

- the chaos-only purpose and current passive state;
- separation from future observation and remediation systems;
- supported Python and container prerequisites;
- dependency synchronization and quality-gate commands;
- CLI commands and JSON output mode;
- each Phase 1 environment variable;
- local versus container defaults;
- building, starting, inspecting, and stopping the Compose service;
- what container health does and does not mean;
- data-volume ownership and persistence;
- future SSH mount locations without real credentials;
- safe log handling; and
- features intentionally deferred to Phase 2 and later.

## 14. Phase 2 handoff contract

Phase 1 must leave these stable seams for Phase 2:

- configuration can add target and SSH sections without changing existing environment semantics unexpectedly;
- the CLI can add `preflight` without moving business logic into Typer callbacks;
- adapters can be added without domain code importing infrastructure libraries;
- container images can add an SSH client without changing the non-root security posture;
- individual SSH identity and known-hosts files can be mounted read-only;
- logs can add target and operation identifiers while retaining sanitization; and
- the passive runtime can become an experiment worker without introducing a second long-running process model.

Phase 2 owns all remote access, target identity, and `sudo` contract decisions.

## 15. Risks, assumptions, and deferred decisions

### Risks

- A passive runtime may be overengineered if it grows beyond heartbeat and shutdown responsibilities. Keep it deliberately small.
- Read-only root filesystems can reveal dependencies that write to unexpected locations. Tests must catch this early.
- Bind-mounted data can fail due to host UID/GID ownership. Document and test the expected deployment approach.
- Lock-file and container build behavior can diverge if the build bypasses the documented dependency workflow.
- Health output can accidentally overstate system readiness. Use explicit local-agent terminology.

### Assumptions

- The control VM can run a modern Docker Engine with Compose support.
- The deployment can provide persistent storage writable by the container's fixed non-root identity.
- Python 3.12 is acceptable for both development and container builds.
- No inbound service port is required until the API phase.
- The initial container is continuously running so later experiment expiry and reconciliation can build on the same process model.

### Deferred decisions

- SSH library or system-client implementation details: Phase 2.
- Target identity mechanism and remote helper design: Phase 2.
- SQLAlchemy models and schema migration tool: Phase 3.
- Experiment worker scheduling and concurrency implementation: Phase 3.
- HTTP website observation implementation: Phase 3.
- API authentication and authorization: Phase 8.
- Dashboard technology: Phase 9.

## 16. Approval to begin implementation

Implementation may begin after this specification is accepted and any requested changes are committed. Starting Step 1 does not authorize remote access, chaos injection, credential creation, or deployment to a VM.
