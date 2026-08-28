# Chaos Agent Project Guidance

## Project purpose

Build a containerized Python chaos agent that runs on its own VM and injects controlled, time-bounded incidents into an isolated development web VM over SSH. The target currently hosts a static site on Apache.

The chaos agent creates faults only. A future, separate remedy agent will detect, diagnose, and repair incidents. Do not add remediation logic to the chaos agent. Automatic experiment expiry and cleanup are safety mechanisms, not remediation.

## Product direction

Start with a dependable command-line application. Keep the core behavior independent of Typer so the same application services can later be exposed through FastAPI and launched or monitored from a dashboard.

The intended progression is:

1. Typer CLI for local operation on the chaos-agent VM.
2. Persistent experiment state and history.
3. FastAPI service using the same core application layer.
4. Dashboard for launching experiments and monitoring the agent, target, and site.

Do not build the dashboard until the scenario runner and safety behavior are proven.

## Technology preferences

- Python 3.12 or newer.
- Typer for the initial CLI.
- Pydantic for configuration, scenario parameters, and validation.
- SQLAlchemy with SQLite for initial persistence.
- HTTPX for external website health checks.
- Pytest for automated testing.
- SSH for communication with the target VM.
- Use a transport abstraction so SSH implementation details do not leak into scenario logic.

Prefer clear, typed Python. Keep domain and application logic separate from CLI, database, SSH, and HTTP adapters.

## Container-first deployment

The chaos agent must be easy to deploy as a container on its dedicated VM.

- Provide a production-oriented Dockerfile and a simple Compose configuration when implementation begins.
- Run the application as a non-root user inside the container.
- Do not mount the Docker socket.
- Inject secrets at runtime; never bake SSH keys or credentials into an image.
- Mount the SQLite database and audit data on persistent storage.
- Mount the SSH key and known-hosts data read-only.
- Enforce strict SSH host-key checking.
- Ensure experiment execution is not coupled to an interactive terminal or container shell.
- Handle termination signals cleanly and preserve enough state for cleanup or reconciliation after restart.
- Add a container health check that reports agent health without claiming the target site is healthy.

The container is the control plane. Chaos workloads execute only on the allowlisted development target through approved remote operations.

## Security model

- Connect to the dev VM with a dedicated, unprivileged account.
- Give that account narrowly scoped `sudo` permissions for approved chaos operations only.
- Never require root SSH login or unrestricted passwordless `sudo`.
- Never expose an arbitrary remote-shell feature through the CLI, API, scenarios, or configuration.
- Use an explicit target allowlist and validate target identity before every experiment.
- Refuse to operate if the target cannot be positively identified as the configured development VM.
- Treat all scenario parameters as untrusted input and validate them before constructing remote commands.
- Avoid shell interpolation. Prefer fixed helper commands with validated arguments.
- Store secrets outside the repository and redact them from logs and database records.
- Permit only one active experiment per target in the first version.

## Initial scenarios

Implement only these scenarios initially:

1. Stop Apache.
2. Create bounded CPU pressure.
3. Create bounded disk pressure in a dedicated test location or filesystem.

Memory pressure, network disruption, root-filesystem pressure, and other higher-risk scenarios are out of the initial scope.

Each scenario must define:

- A stable scenario name and description.
- Required target capabilities and preconditions.
- Strictly typed and bounded parameters.
- The exact injection operation.
- Expected observable symptoms.
- A mandatory maximum duration.
- Idempotent emergency cleanup.
- Post-cleanup verification.
- Audit fields that explain what happened without leaking secrets.

Scenario implementations must not contain the remedy that a future remedy agent is expected to discover and perform. Cleanup should withdraw only artifacts or processes created by the chaos experiment, except where an explicit emergency safety action is necessary.

## Safety invariants

Safety requirements take priority over feature delivery.

- Every experiment requires a maximum duration; never allow an unlimited run.
- Use a conservative default duration of five minutes and a configurable hard upper bound.
- Run preflight checks before injection.
- Refuse to start when the target or site is already unhealthy, unless a future explicit diagnostic mode is designed for that purpose.
- Record sufficient state before injection to support cleanup after a process or container restart.
- Make cleanup safe to retry.
- Maintain resource reserves for SSH access, logging, and cleanup.
- Disk pressure must target dedicated test storage and must not fill the root filesystem.
- CPU pressure must be capped and leave capacity for management access.
- Do not implement memory pressure until its OOM and recovery behavior has a separately reviewed design.
- If injection succeeds only partially, transition immediately to cleanup and record the experiment as failed.
- If cleanup cannot be confirmed, clearly mark the experiment as requiring operator attention.

## Observation boundaries

The chaos agent may observe the site to establish test evidence, but observation must remain distinct from fault injection.

For each experiment, perform external checks from the chaos-agent VM or container:

- Before injection, confirm the configured URL is healthy.
- During the experiment, record HTTP availability, status, latency, and failures.
- After cleanup, confirm the expected HTTP status and optional content marker.

Health checks must have timeouts and bounded retries. They must not repair the target.

A future independent observer may replace or supplement these built-in checks. Keep observation behind an interface so this can evolve without changing scenario implementations.

## Experiment lifecycle

Use an explicit state machine. At minimum, support states equivalent to:

`planned -> preflight -> injecting -> active -> cleaning_up -> verifying -> passed/failed`

Also represent cancellation, expired experiments, cleanup failure, and operator attention explicitly. Persist state transitions with timestamps. Do not infer success merely because a command returned zero; verify the intended system effect.

## Persistence and audit history

Use SQLite initially through SQLAlchemy. Keep persistence behind repository interfaces so a later service deployment can move to another database.

Record at least:

- Experiment ID and scenario version.
- Target identifier.
- Validated parameters.
- Initiator.
- State transitions and timestamps.
- Preflight result.
- Injection result.
- Website observations.
- Expiration and cleanup attempts.
- Final verification and outcome.
- Sanitized diagnostic output.

Do not store private keys, passwords, tokens, or unsanitized environment variables.

## CLI expectations

The initial Typer interface should evolve toward commands such as:

- `chaos list`
- `chaos preflight`
- `chaos run <scenario>`
- `chaos status [experiment-id]`
- `chaos abort <experiment-id>`
- `chaos history`
- `chaos reconcile`

Commands should call application services and contain minimal business logic. Support machine-readable output where practical so automation and the future API can reuse behavior without parsing decorative terminal text.

## Testing expectations

- Write unit tests for scenario validation, state transitions, safety policy, and cleanup idempotency.
- Use fakes for SSH, clocks, HTTP checks, and persistence in fast tests.
- Add integration tests that exercise SQLite and command construction without requiring a real VM.
- Put real target tests behind explicit opt-in markers and environment checks.
- Never run a destructive or disruptive test against a host based only on a hostname supplied by a test environment variable.
- Test timeout, partial-injection, agent-restart, and repeated-cleanup paths.
- Verify logs and persisted records do not expose secrets.

## Development practices

- Keep changes small and testable.
- Prefer explicit configuration over hidden environment-dependent behavior.
- Document threat and failure assumptions when adding a scenario.
- Do not broaden SSH or `sudo` privileges to make implementation easier.
- Do not add autonomous scenario selection in the initial version.
- Do not add arbitrary AI-generated commands. Any future model-assisted feature must select from validated, allowlisted actions.
- Update user-facing documentation when commands, configuration, safety limits, or deployment behavior changes.

## Git workflow

- Treat each implementation step as a small, independently verifiable change.
- Inspect repository status before starting a step. If unrelated or unexplained changes are present, preserve them and resolve ownership with the user before proceeding.
- After completing a step, run the relevant tests and checks before committing.
- Update documentation and the implementation specification when the completed step changes either one.
- Commit each completed step with a concise message that describes the delivered outcome.
- Include only files belonging to the completed step in its commit. Never sweep unrelated user changes into a commit.
- Confirm the working tree is clean after the commit and before yielding for the next prompt.
- Never discard, overwrite, reset, or amend user-owned work merely to make the tree clean.
- If a step cannot be completed, tested, or committed safely, report the blocker instead of creating a misleading completion commit.
- Do not rewrite published history or force-push unless the user explicitly requests it.

## Definition of done for an initial scenario

An initial scenario is complete only when it has validated parameters, preflight checks, bounded injection, persisted state, external health observations, automatic expiry, retry-safe cleanup, post-cleanup verification, audit history, and tests covering both success and failure paths.
