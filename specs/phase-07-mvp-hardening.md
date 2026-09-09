# Phase 7 Specification: MVP Hardening

## 1. Purpose

Phase 7 turns the first three scenarios into an operationally dependable CLI MVP. It validates the complete lifecycle across Apache stop, CPU pressure, and dedicated-storage disk pressure; hardens restart, failure, persistence, and container behavior; and gives operators the runbooks and release procedures needed to use the chaos agent safely.

Phase 7 does not add new chaos types, autonomous scenario selection, an API, a dashboard, or remedy logic.

## 2. MVP scope

The supported production catalog contains exactly:

- `apache-stop`;
- `cpu-pressure`; and
- `disk-pressure`.

Each scenario must satisfy the definition of done in `AGENTS.md`: typed and bounded parameters, positive preflight, bounded injection, durable lifecycle state, external observations, automatic expiry, retry-safe cleanup, post-cleanup verification, audit history, and tests covering success and failure paths.

The control plane remains a non-root container with no Docker socket, no inbound port, strict SSH host verification, persistent local SQLite storage, and read-only SSH material mounts.

## 3. Hardening invariants

- No scenario runs without a healthy, positively identified development target baseline.
- Every experiment has a mandatory bounded duration and one-active-experiment-per-target protection.
- The supervisor, not the CLI or terminal session, owns execution, expiry, observation, and cleanup.
- Restart reconciliation never reinjects an uncertain or previously active experiment.
- Cleanup never targets artifacts or processes whose ownership cannot be proven.
- Cleanup failure and verification uncertainty remain visible as `operator_attention`.
- Target and website health remain distinct from local agent health.
- Logs, database records, CLI output, images, and backups contain no credentials, raw command output, or unbounded data.
- The agent never broadens its own SSH or sudo privileges.
- No real-target action occurs without explicit opt-in and an approved development target.

## 4. Operational test matrix

### 4.1 Scenario lifecycle matrix

For every supported scenario, test:

- healthy preflight and successful scheduling;
- injection and positive effect verification;
- bounded during observations;
- normal expiry and automatic cleanup;
- operator abort and durable cancellation;
- repeated cleanup;
- injection timeout and partial injection;
- cleanup timeout, retry, and exhausted retries;
- unhealthy before and after observations;
- agent restart in every mutating lifecycle state;
- lease expiration and competing supervisor behavior; and
- final audit history and machine-readable output.

### 4.2 Environment and persistence drills

Exercise in a disposable environment:

- container recreation with persistent SQLite history;
- graceful container stop during an active experiment;
- forced termination followed by cleanup-first reconciliation;
- host restart and stale lease recovery;
- stale lock or abandoned owner handling;
- database backup, restore, and migration upgrade;
- malformed or newer schema refusal;
- corrupted or incomplete cleanup context;
- full or unavailable target transport;
- unavailable website observer; and
- log rotation or bounded evidence growth.

No drill may use an unapproved real target by default.

## 5. Release and configuration hardening

### 5.1 Configuration

Verify that defaults are conservative, invalid combinations are rejected, secrets are supplied only at runtime, and target identity is never inferred from host reachability. Document every supported environment variable, its bounds, and whether changing it requires a restart or migration.

### 5.2 Container

The release image must:

- run as the documented non-root UID/GID;
- use a read-only root filesystem;
- drop all capabilities and forbid privilege escalation;
- contain no source tests, Git metadata, keys, credentials, operational target data, or build tools;
- mount only the documented persistent data and read-only SSH/CA material;
- provide a health check that reports local agent health only; and
- stop within the cleanup grace period or leave durable state for reconciliation.

### 5.3 Database

Use explicit Alembic migrations. Before upgrades, stop the agent and create a consistent SQLite backup using the SQLite backup API or an equivalent database-aware operation; never copy a live WAL database blindly. Verify restored backups read-only before use. Refuse startup when the schema is newer than the application or requires an unapplied migration.

### 5.4 Audit and redaction

Audit records must distinguish injection, target impact, emergency cleanup, remedy-independent recovery verification, and operator intervention. Verify bounded field sizes, stable categories, ordered transitions, and absence of private keys, passwords, tokens, raw process arguments, response bodies, and complete remote output.

## 6. CLI contract

Finalize and test the following commands:

```text
chaos list [--json]
chaos preflight [--json]
chaos run <scenario> --initiator NAME [--duration SECONDS] [--json]
chaos status [EXPERIMENT_ID] [--json]
chaos abort <EXPERIMENT_ID> --initiator NAME [--json]
chaos history [--scenario NAME] [--state STATE] [--limit N] [--json]
chaos reconcile [EXPERIMENT_ID] [--initiator NAME] [--json]
chaos health [--json]
chaos config-check [--json]
```

Human and JSON output must clearly distinguish scheduled, active, expired, cleaning, failed, cancelled, and operator-attention states. Exit codes must be stable and documented. The CLI must never perform target mutation or cleanup synchronously as a side effect of rendering status.

## 7. Runbooks

Provide concise, tested operator runbooks for:

- initial deployment and configuration;
- independent host-fingerprint verification;
- target provisioning and narrow sudo review;
- preflight refusal diagnosis;
- scenario launch and observation;
- abort and emergency cleanup;
- reconciliation after agent or host restart;
- cleanup failure and operator attention;
- SQLite backup, restore, migration, and rollback;
- SSH key and known-host rotation;
- stale lease or database recovery;
- container health degradation;
- incident evidence collection; and
- safe rollback and complete removal of the control plane.

Runbooks must identify which actions belong to the chaos agent, which belong to an operator, and which belong to the future remedy system. They must never instruct an operator to bypass target identity, broaden sudo, disable host-key checking, or use arbitrary remote commands.

## 8. Release process

The MVP release must include:

- version and supported Python range;
- locked dependencies and reproducible image inputs;
- release notes describing supported scenarios and limitations;
- documented upgrade and downgrade constraints;
- database backup requirements;
- a clean deployment procedure from a fresh checkout;
- a tested rollback procedure;
- explicit deferred risks, including memory and network chaos; and
- a statement that no remedy behavior is included.

Do not publish or push credentials, target markers, fingerprints, databases, runtime data, or real-target evidence containing sensitive information.

## 9. Testing requirements

### 9.1 Automated quality gates

Require passing:

- unit and integration tests;
- strict type checking;
- lint and formatting checks;
- migration upgrade and downgrade checks where supported;
- package and wheel build;
- target helper and dispatcher contract tests;
- container image inspection;
- Compose configuration validation;
- container smoke tests; and
- repository secret and artifact scans.

### 9.2 Failure-injection tests

Use deterministic fakes for clocks, transport, HTTP, persistence, leases, filesystem facts, workload control, and target services. Prove that every failure path preserves expiry and cleanup priority and cannot produce a false passed outcome.

### 9.3 Guarded real-target validation

Real-target tests remain opt-in and require explicit acknowledgement, independently verified host key and target UUID, a development-only marker, clean preflight, operator observation, and a documented recovery path. Run scenarios one at a time and inspect audit history afterward. A real-target test is not a release prerequisite if the approved disposable contract and all local safety gates pass, but its absence must be recorded clearly.

## 10. Acceptance criteria

Update each item only after concrete evidence exists:

- [ ] Apache-stop, CPU-pressure, and disk-pressure each meet the complete definition of done.
- [ ] All supported scenario parameters and target operations are strictly bounded and documented.
- [ ] The full lifecycle matrix passes for all three scenarios.
- [ ] Expiry, abort, restart, lease loss, partial injection, cleanup retry, and operator-attention paths are deterministic.
- [ ] No cleanup path can affect an unrelated service, process, path, filesystem, or artifact.
- [ ] Before, during, and after observations are bounded, persisted, and distinguishable from injection evidence.
- [ ] SQLite backup, restore, migration, schema refusal, and recovery procedures are tested.
- [ ] Container recreation preserves required history and retains all hardening restrictions.
- [ ] CLI human and JSON contracts, exit codes, and audit output are stable and documented.
- [ ] Logs, database records, image contents, repository contents, and release artifacts contain no secrets or operational target data.
- [ ] Python, type, lint, package, migration, helper, Compose, image, container, and artifact-scan gates pass.
- [ ] All required operator runbooks are complete and tested from a clean deployment.
- [ ] Release notes document supported behavior, deferred risks, rollback, and remedy boundaries.
- [ ] No API, dashboard, autonomous selection, memory chaos, or network chaos is included.
- [ ] A clean working tree and reproducible release artifact are produced for the MVP release.

## 11. Approval to begin implementation

Creating this specification does not authorize implementation, real-target access, disruptive experiments, release publication, or privilege changes. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
