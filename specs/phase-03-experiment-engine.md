# Phase 3 Specification: Experiment Engine

## Status

In progress — Steps 1–2 complete.

## 1. Purpose and measurable outcome

Phase 3 builds the persistent, restart-safe lifecycle engine required by every chaos scenario. It turns the passive `chaos agent` process into a supervisor that can claim scheduled experiments, enforce a mandatory duration, record observations and state transitions, react to cancellation or expiry, run retry-safe cleanup, verify the final condition, and reconcile interrupted work after restart.

Phase 3 does not add a production chaos scenario or any new write-capable target-helper operation. The engine is proven with fakes and a test-only synthetic scenario that cannot enter the production scenario catalog.

The measurable outcome is an engine that can demonstrate, without contacting a real VM, that:

- every experiment is durably recorded before work begins;
- only one non-terminal experiment can exist for a target;
- execution continues under the supervised agent rather than a CLI terminal;
- preflight must pass before injection;
- injection is never resumed blindly after an uncertain interruption;
- cancellation and expiry always converge on cleanup;
- cleanup is safe to retry and every attempt is audited;
- cleanup or verification uncertainty becomes explicit operator attention;
- before, during, and after website observations are persisted separately from fault actions; and
- an agent restart deterministically reconciles every non-terminal state.

## 2. Scope

### 2.1 In scope

- Strict domain models for scenarios, experiment requests, lifecycle state, transition reasons, cleanup context, observations, and outcomes.
- An explicit transition policy with no unrestricted state setter.
- SQLAlchemy 2.x persistence using SQLite on the existing persistent data volume.
- Alembic migrations and explicit schema compatibility checks.
- Durable experiments, transitions, action attempts, observations, cancellation requests, and reconciliation evidence.
- A database-enforced one-active-experiment-per-target invariant.
- Optimistic concurrency and agent ownership leases for safe claiming.
- Mandatory experiment duration, a five-minute default, and a conservative configurable hard maximum.
- A scenario interface that exposes only typed lifecycle operations.
- A production scenario registry that is empty until Phase 4.
- A test-only synthetic scenario used exclusively through dependency injection.
- Application services for scheduling, querying, cancellation requests, history, and reconciliation requests.
- A background supervisor integrated into `chaos agent`.
- Automatic expiry, bounded cleanup retries, post-cleanup verification, and operator-attention outcomes.
- Restart reconciliation rules for every non-terminal state.
- Persisted before, during, and after HTTP observations behind the existing observation boundary.
- Human-readable and versioned JSON CLI output for scenario list, run, status, history, abort, and reconcile.
- Container lifecycle, persistence, signal, restart, and SQLite safety tests.

### 2.2 Out of scope

- Stopping, starting, restarting, or reloading Apache.
- CPU, disk, memory, process, firewall, DNS, route, or network fault injection.
- Any new target-side helper operation or `sudoers` permission.
- A production no-op or demo scenario that could be confused with a completed chaos experiment.
- Selecting a scenario autonomously or generating a remote command with a model.
- Multiple simultaneous experiments on one target.
- Multiple agent replicas actively supervising the same SQLite database.
- Distributed locking or a network database.
- FastAPI, dashboard, authentication, or remote multi-user scheduling.
- Remedy logic or judging remedy-agent success.
- Treating emergency cleanup as successful remediation.
- A destructive or disruptive real-target test.

Phase 3 may reuse Phase 2 read-only preflight and website observation. It is not authorized to provision a target or expand target privileges.

## 3. Decisions fixed by this specification

### 3.1 Execution ownership

The long-running `chaos agent` process is the only component that executes lifecycle work. CLI commands are short-lived application adapters:

- `chaos run` validates and durably schedules an experiment, then returns its ID;
- `chaos abort` records a cancellation request;
- `chaos reconcile` records or exposes a reconciliation request; and
- `chaos status`, `chaos history`, and `chaos list` are read-only.

CLI disconnection, terminal closure, or SSH logout from the control VM must not stop an active experiment or its expiry timer. Typer contains rendering and exit-code mapping only.

### 3.2 Production scenario catalog

The production registry is empty in Phase 3. `chaos list` may report that no production scenarios are installed, and `chaos run <name>` must reject every unknown or unavailable scenario without creating an experiment.

Tests inject a synthetic scenario registry directly into application services. The synthetic scenario:

- has no SSH or subprocess adapter;
- mutates only fake in-memory test state;
- is excluded from installed runtime registration; and
- cannot be enabled through environment variables or CLI input.

Phase 4 will register `apache-stop` only after its helper, privilege, preflight, injection, and cleanup contract receives a separate review.

### 3.3 Persistence technology

Use synchronous SQLAlchemy 2.x repositories with SQLite and Alembic migrations.

- Store the database at `${CHAOS_DATA_DIR}/chaos-agent.db` by default.
- Keep ORM models inside the persistence adapter; domain and application layers depend on repository protocols.
- Enable SQLite foreign keys, WAL journal mode, a bounded busy timeout, and durable synchronization.
- Create the database with mode `0600` beneath the existing mode-`0700` data directory.
- Refuse startup when the schema is newer than the application or requires an unapplied migration.
- Apply upgrades through an explicit documented command; never downgrade automatically.
- Migration and schema checks must not read or modify SSH material.

SQLite is suitable for one supervisor process and local CLI readers/writers. A later API deployment may replace the adapter without changing lifecycle policy.

### 3.4 Time model

Persist timezone-aware UTC timestamps. Inject a clock interface into application services and tests.

- `requested_duration_seconds` is immutable after scheduling.
- `expires_at` is calculated and persisted before injection begins.
- The in-process runner may use monotonic time for waits.
- Restart reconciliation uses persisted UTC deadlines because monotonic values do not survive restart.
- Backward wall-clock movement must never extend an already persisted expiry.
- If the current time is at or after `expires_at`, cleanup takes precedence over all active work.

### 3.5 Concurrency model

Phase 3 supports one active supervisor process. It still defends against duplicate CLI requests and accidental second processes:

- a partial unique SQLite index prevents more than one non-terminal experiment per target;
- scheduling and claiming are transactions;
- each experiment row has a revision used for optimistic updates;
- a claim records `owner_instance_id`, `lease_acquired_at`, and `lease_expires_at`;
- lease renewal is periodic and bounded;
- a stale lease never authorizes resuming injection; it triggers reconciliation; and
- loss of a lease causes the runner to stop forward progress and move toward cleanup or operator attention.

Do not rely on an in-memory mutex as the safety invariant.

## 4. Architecture and dependency boundaries

```text
Typer CLI
   -> scheduling/query/cancellation application services
      -> repository interfaces
         -> SQLAlchemy + SQLite adapter

chaos agent supervisor
   -> experiment coordinator
      -> transition policy
      -> scenario registry and typed scenario interface
      -> Phase 2 preflight service
      -> site observer interface
      -> repository interfaces
      -> clock and wait interfaces
```

Suggested additions:

```text
src/chaos_agent/
├── domain/
│   ├── experiment.py
│   └── scenario.py
├── application/
│   ├── experiments.py
│   ├── supervisor.py
│   └── ports.py
└── adapters/
    └── persistence/
        ├── database.py
        ├── models.py
        └── repositories.py

alembic.ini
migrations/
├── env.py
└── versions/
```

Rules:

- Domain code imports no Typer, SQLAlchemy, SQLite, HTTPX, subprocess, or container details.
- Scenario implementations receive typed ports, never a database session or arbitrary transport command.
- Repositories return domain records or immutable data-transfer models, not ORM objects.
- The supervisor coordinates services; it does not embed scenario-specific commands.
- Persistence transactions do not remain open across SSH, HTTP, sleeps, or cleanup actions.
- Every external action has an idempotency identity derived from the immutable experiment ID and scenario version.

## 5. Domain contract

### 5.1 Experiment identity

Use opaque IDs formatted as `exp_<32 lowercase hexadecimal characters>` generated from cryptographically random UUID4 values. Validate IDs strictly at every CLI and repository boundary. IDs are not secrets.

Each experiment records:

- experiment ID;
- target UUID and sanitized target label;
- stable scenario name and semantic scenario version;
- canonical validated parameters;
- requested duration and absolute expiry;
- initiator;
- current state and row revision;
- ownership lease fields;
- cancellation metadata;
- cleanup context version and sanitized context;
- final outcome and attention reason;
- created, updated, started, and completed timestamps; and
- the application version that created it.

### 5.2 Lifecycle states

Use these stable states:

| State | Meaning |
| --- | --- |
| `planned` | Durable request exists but no target work has begun |
| `preflight` | Phase 2 and scenario-specific read-only checks are running |
| `injecting` | Injection was requested; its final effect may be uncertain |
| `active` | Injection effect was positively verified |
| `cancellation_requested` | Operator requested early termination |
| `expired` | Persisted duration elapsed |
| `cleaning_up` | Emergency cleanup is being attempted |
| `verifying` | Cleanup and expected final baseline are being verified |
| `passed` | Full requested experiment completed and cleanup verified |
| `cancelled` | Operator cancellation completed and cleanup verified |
| `failed` | Work failed before mutation, or failed after cleanup and final safety were verified |
| `cleanup_failed` | A cleanup attempt failed and retry policy remains relevant |
| `operator_attention` | Safety cannot be confirmed automatically |

Terminal states are `passed`, `cancelled`, `failed`, and `operator_attention`. `cleanup_failed` is non-terminal until retry policy moves it back to `cleaning_up` or escalates it to `operator_attention`.

### 5.3 Transition policy

The allowed graph is:

```text
planned -> preflight | cancelled
preflight -> injecting | failed | cancelled
injecting -> active | cleaning_up
active -> expired | cancellation_requested | cleaning_up
cancellation_requested -> cleaning_up
expired -> cleaning_up
cleaning_up -> verifying | cleanup_failed
cleanup_failed -> cleaning_up | operator_attention
verifying -> passed | cancelled | failed | operator_attention
```

Additional rules:

- No terminal state can transition.
- Every transition records the prior state, next state, UTC time, reason code, actor, and row revision.
- A preflight refusal reaches `failed` only because injection never began; it is not a successful experiment.
- Once `injecting` is persisted, any exception or restart assumes partial injection and enters cleanup.
- `active` is allowed only after scenario-specific effect verification.
- `passed` is allowed only for normal expiry or completed duration with successful cleanup and verification.
- A cancellation can end only as `cancelled`, `failed`, or `operator_attention`, never `passed`.
- Cleanup success alone is insufficient; post-cleanup verification is mandatory.
- Direct repository updates that bypass the transition policy are forbidden.

### 5.4 Scenario interface

Define a typed scenario contract with:

- stable `name`, `version`, and description;
- Pydantic parameter model and JSON schema;
- maximum supported duration bounded by the engine hard maximum;
- required target capabilities;
- `preflight(context)`;
- `inject(context)` returning a versioned cleanup context;
- `verify_active(context)`;
- `cleanup(context, cleanup_context)` safe to repeat; and
- `verify_cleanup(context, cleanup_context)`.

Results contain stable status and sanitized evidence only. A scenario cannot:

- accept a raw command, executable, path, host, SSH option, or environment dictionary;
- write directly to the experiment database;
- suppress expiry or cleanup;
- mark its own experiment passed;
- register itself from configuration or dynamic imports; or
- expose cleanup context to a future remedy agent.

The engine persists enough cleanup context before accepting `active`. If injection returns only partial context or its persistence fails, the coordinator immediately enters cleanup using the immutable experiment ID and all safely available context.

## 6. Persistence and audit schema

### 6.1 Tables

At minimum provide:

`experiments`

- authoritative current state, immutable request fields, lease, revision, expiry, cleanup context, and final outcome;
- partial unique index on target ID for all non-terminal states; and
- indexes for state, scenario, created time, expiry, and target history.

`experiment_transitions`

- append-only transition sequence with unique `(experiment_id, sequence)`;
- from/to state, timestamp, reason, actor, and sanitized summary; and
- no update or delete through normal repositories.

`action_attempts`

- preflight, injection, active verification, cleanup, final verification, and reconciliation attempts;
- start/completion timestamps, attempt number, stable result category, and sanitized evidence; and
- unique idempotency key per experiment, action kind, and attempt.

`site_observations`

- phase (`before`, `during`, or `after`), sequence, timestamp, availability, status, latency, content match, and safe failure category;
- no response body, URL credentials, headers, cookies, or raw exception text; and
- unique `(experiment_id, phase, sequence)`.

`control_requests`

- cancellation and reconciliation requests with requester, timestamp, processing state, and idempotency key.

### 6.2 Transactional rules

- Insert an experiment and its initial `planned` transition atomically.
- Transition current state and append its audit row atomically.
- Persist `injecting` before invoking injection.
- Persist cleanup context and the transition to `active` atomically after positive effect verification.
- Persist cancellation requests before acknowledging the CLI.
- Use compare-and-swap revision checks for claims and transitions.
- Treat uniqueness or revision conflicts as safe refusals, not reasons to retry an action blindly.
- Never hold a write transaction while waiting on target or website I/O.

### 6.3 Sanitization

Persist allowlisted evidence fields only. Never persist:

- private-key, password, token, cookie, authorization, or environment values;
- raw SSH stdout or stderr;
- HTTP response bodies or headers;
- complete subprocess argument arrays;
- tracebacks; or
- unvalidated scenario input.

Limit individual diagnostic strings to 256 characters, JSON parameter or cleanup documents to 16 KiB each, and total evidence per action attempt to a conservative documented bound.

## 7. Duration, expiry, cancellation, and cleanup

### 7.1 Duration policy

Add configuration equivalent to:

| Setting | Default | Rule |
| --- | --- | --- |
| `CHAOS_DEFAULT_EXPERIMENT_DURATION_SECONDS` | `300` | 10–900 |
| `CHAOS_MAX_EXPERIMENT_DURATION_SECONDS` | `900` | 30–3600 and at least the default |
| `CHAOS_SUPERVISOR_POLL_INTERVAL_SECONDS` | `1` | 1–10 |
| `CHAOS_LEASE_DURATION_SECONDS` | `30` | 10–120 |
| `CHAOS_LEASE_RENEW_INTERVAL_SECONDS` | `10` | less than half the lease duration |
| `CHAOS_CLEANUP_MAX_ATTEMPTS` | `3` | 1–10 |
| `CHAOS_CLEANUP_RETRY_BASE_SECONDS` | `2` | 1–30, bounded exponential backoff |
| `CHAOS_OBSERVATION_INTERVAL_SECONDS` | `5` | 1–60 |
| `CHAOS_SHUTDOWN_CLEANUP_GRACE_SECONDS` | `60` | 10–300 |

Every request includes a resolved duration. Unlimited, zero, negative, overflowed, or above-policy durations are rejected before persistence.

### 7.2 Cancellation

`chaos abort <experiment-id>` records an idempotent cancellation request.

- Planned or preflight work stops before injection and ends `cancelled` only when no mutation occurred.
- Injecting or active work transitions through `cancellation_requested` and cleanup.
- Repeated abort requests do not create duplicate cleanup actions.
- Aborting a terminal experiment returns its existing terminal result without mutation.
- The CLI does not perform cleanup itself.

### 7.3 Cleanup retry policy

- Cleanup is mandatory after normal expiry, cancellation, partial injection, active verification failure, lease loss after injection, or restart from an uncertain mutating state.
- Cleanup receives only the immutable experiment identity and persisted typed cleanup context.
- Every attempt has a hard timeout defined by the scenario contract and engine ceiling.
- Retry uses bounded exponential backoff and persists the next eligible time.
- Successful cleanup proceeds to verification even if an earlier attempt failed.
- Exhausted automatic attempts transition to `operator_attention` with a stable reason.
- A later explicit reconcile request may authorize another bounded attempt and is fully audited.
- No cleanup path may target artifacts not owned or identified by the experiment.

## 8. Observation lifecycle

Observation is evidence, not injection or remediation.

- Persist a healthy `before` observation after target/scenario preflight and before `injecting`.
- During `active`, sample at the configured bounded interval until cancellation or expiry.
- Persist one `after` observation during final verification after cleanup.
- Use the existing site observer interface and safe categories.
- An unhealthy `before` observation refuses injection.
- A failed `during` observation is evidence and does not disable expiry or cleanup.
- A failed `after` observation prevents `passed` or `cancelled`; final state is `failed` when cleanup is otherwise verified, or `operator_attention` when target safety is uncertain.
- Bound observation count from duration and interval; never create an unbounded sampling loop.

A future independent observer may consume audit data, but Phase 3 does not publish hidden injection details to a remedy agent.

## 9. Supervisor behavior

### 9.1 Startup

On `chaos agent` startup:

1. Validate configuration and database schema.
2. Create a unique runtime instance ID.
3. Inspect every non-terminal experiment before claiming new work.
4. Reconcile stale or missing leases according to persisted state.
5. Only then claim the oldest eligible `planned` experiment.

### 9.2 Reconciliation matrix

| Persisted state | Restart behavior |
| --- | --- |
| `planned` | Eligible for a fresh claim |
| `preflight` | Re-run read-only preflight from the beginning |
| `injecting` | Assume partial injection; go directly to cleanup |
| `active` | If expired, cancel-requested, or lease uncertain, go to cleanup; never re-inject |
| `cancellation_requested` | Go directly to cleanup |
| `expired` | Go directly to cleanup |
| `cleaning_up` | Retry the same idempotent cleanup using persisted context |
| `cleanup_failed` | Retry when eligible or escalate after the configured limit |
| `verifying` | Re-run cleanup verification and after observation; never re-inject |

Terminal experiments are never reclaimed.

### 9.3 Shutdown

On `SIGINT` or `SIGTERM`:

- stop claiming new work;
- persist a shutdown/cancellation reason for active work;
- attempt cleanup within the configured grace period;
- renew the lease while cleanup is progressing;
- persist the latest safe state before exit; and
- exit non-zero or degraded if cleanup safety cannot be confirmed.

The Compose stop grace period must exceed the engine cleanup grace. Forced container termination remains recoverable through restart reconciliation and must never produce a false terminal success.

## 10. Application service contract

Provide services equivalent to:

- `ScenarioCatalog.list()`;
- `ScheduleExperiment.schedule(request)`;
- `GetExperiment.get(id)`;
- `ListExperimentHistory.list(filters, cursor, limit)`;
- `RequestCancellation.request(id, initiator, idempotency_key)`;
- `RequestReconciliation.request(id_or_all, initiator)`; and
- `Supervisor.run()` / `Supervisor.run_once()`.

Service responses are typed and serialization-ready. Pagination is bounded and deterministic by `(created_at, experiment_id)`. Application services never render terminal text.

## 11. CLI contract

Add or complete:

```text
chaos list [--json]
chaos run <scenario> [--duration SECONDS] --initiator NAME [--json]
chaos status [experiment-id] [--json]
chaos history [--scenario NAME] [--state STATE] [--limit N] [--json]
chaos abort <experiment-id> --initiator NAME [--json]
chaos reconcile [experiment-id] --initiator NAME [--json]
```

Phase 3 behavior:

- `list` returns an empty production catalog until Phase 4.
- `run` rejects unavailable scenarios and creates no database row.
- `status` without an ID shows the active experiment, if any.
- `history` is read-only and bounded to at most 100 records per call.
- `abort` and `reconcile` acknowledge durable requests, not completed cleanup.
- Human and JSON output clearly distinguish requested, running, terminal, cleanup-failed, and operator-attention states.

Exit codes:

- `0`: request accepted or query completed;
- `1`: safety refusal, conflict, unavailable scenario, or invalid lifecycle operation;
- `2`: invalid configuration or CLI input;
- `3`: persistence, supervisor, or internal execution error.

No command accepts a target host, SSH option, remote command, cleanup token, or arbitrary parameter JSON that bypasses the selected scenario model.

## 12. Container and operational behavior

- Persist SQLite and audit state beneath `/var/lib/chaos-agent` on the named volume.
- Keep the root filesystem read-only, UID/GID 10001, dropped capabilities, `no-new-privileges`, no Docker socket, and no inbound port.
- Increase the container stop grace period only to the documented bounded cleanup window.
- Keep `chaos health` local-only, but include supervisor liveness, database compatibility, and whether operator attention exists as distinct local checks.
- Local health must not claim the target or website is healthy.
- A cleanup requiring operator attention should make agent health degraded without causing a restart loop that hides the record.
- Do not run database migrations implicitly during container health checks.
- Document database backup as a consistent SQLite backup operation, not copying a live database file blindly.

## 13. Failure modes and required behavior

| Failure | Required behavior |
| --- | --- |
| Invalid duration or parameters | Reject before persistence; no target action |
| Existing non-terminal target experiment | Database-backed refusal; do not queue a second |
| Database locked | Bounded retry, then safe error; never duplicate an action |
| Schema mismatch | Refuse supervisor start and report migration requirement |
| Preflight refusal | Record `failed`; perform no injection |
| Before observation unhealthy | Record `failed`; perform no injection |
| Injection exception or timeout | Assume partial injection and enter cleanup |
| Cleanup-context persistence failure | Use immutable experiment identity, enter cleanup, require attention if ownership cannot be proven |
| Active verification failure | Enter cleanup immediately |
| Cancellation race with expiry | One transactional transition wins; cleanup runs once idempotently |
| Lease loss before injection | Stop; safe requeue or fail without mutation |
| Lease loss after `injecting` | Stop forward work and reconcile to cleanup |
| Agent/container restart | Apply reconciliation matrix; never re-inject uncertain work |
| Cleanup failure | Persist attempt and retry; never mark passed |
| Cleanup retries exhausted | `operator_attention`; preserve all safe evidence |
| After observation unhealthy | `failed` or `operator_attention`; never passed |
| Logging or observation failure | Preserve expiry and cleanup priority; record bounded safe category |
| Forced process termination | Durable state allows cleanup-first restart reconciliation |

## 14. Security and threat model

- CLI users with write access to the SQLite database or container configuration are trusted operators; file permissions must restrict that access.
- Database contents are untrusted when read. Validate states, scenario names, versions, parameters, and cleanup context before use.
- Never dynamically import a scenario named in the database.
- Registry lookup must match both stable scenario name and supported version.
- A tampered or unknown scenario record transitions to operator attention; it never selects a fallback action.
- SQLAlchemy queries use bound parameters; no SQL string interpolation.
- Cleanup context is typed, versioned, bounded, and scenario-specific.
- The experiment ID is an identifier, not authorization.
- Phase 2 target identity and strict SSH checks run before every experiment, including reconciliation when target access is required.
- If identity cannot be positively re-established during cleanup, do not run a cleanup against an unverifiable target; record operator attention prominently.
- No audit API or CLI output exposes hidden cleanup context by default.

## 15. Test strategy

### 15.1 Domain tests

- Every allowed transition and every forbidden transition.
- Terminal immutability.
- Cancellation and expiry result rules.
- Duration boundaries and overflow.
- Strict experiment IDs, scenario names, versions, parameters, and cleanup context.
- Sanitized and bounded evidence models.

### 15.2 Persistence integration tests

- Fresh migration and schema-version refusal.
- SQLite permissions, foreign keys, WAL, busy timeout, and transaction rollback.
- Atomic experiment plus initial transition.
- Partial unique target lock under concurrent scheduling attempts.
- Optimistic revision conflicts.
- Append-only ordered transitions and attempts.
- Idempotent cancellation and reconciliation requests.
- Observation ordering and pagination.
- Restart from a real on-disk SQLite file.

### 15.3 Coordinator tests with fakes

Use fake scenario, preflight, observer, repository, clock, waiter, and lease adapters. Cover:

- full-duration success;
- preflight and before-observation refusal;
- injection timeout and partial injection;
- active verification failure;
- normal expiry;
- cancellation in every non-terminal state;
- cancellation/expiry race;
- cleanup success, timeout, retry, and exhausted retries;
- repeated cleanup and verification;
- failed after observation;
- lease loss before and after injection;
- database failure at every durability boundary; and
- secret-bearing fake diagnostics never reaching logs or records.

### 15.4 Restart reconciliation tests

Seed each non-terminal state in SQLite, restart a fresh supervisor, and prove the matrix in section 9.2. Explicitly verify that `injecting`, `active`, cancellation, expiry, cleanup, and verification states never call injection again.

### 15.5 CLI and container tests

- Stable human and JSON output and exit codes.
- Empty production scenario catalog and unavailable-scenario refusal without a row.
- CLI exits while scheduled fake work continues under a test supervisor.
- Persistent volume retains history across container recreation.
- Graceful termination attempts cleanup.
- Forced termination followed by restart enters cleanup-first reconciliation.
- Health distinguishes local runtime, database, supervisor, and operator-attention state without claiming website health.

Default tests use no real target and inject no fault. Any later real-target scenario test belongs to its scenario phase and remains explicitly guarded.

## 16. Ordered implementation steps

Each step is an independently verified Git change. Follow `AGENTS.md`: inspect status first, update this specification with evidence, test, commit only related files, and leave the tree clean.

### Step 1: Experiment and scenario domain contracts

Complete. Delivered lifecycle enums, transition policy, opaque IDs, strict requests and context models, sanitized evidence, and the typed scenario interface with exhaustive domain tests. No SQLAlchemy or production scenario was added.

### Step 2: SQLite persistence and migrations

Complete. Added SQLAlchemy and Alembic dependencies, SQLite engine hardening, ORM mappings, a baseline migration, transactional experiment repositories, the active-target uniqueness constraint, optimistic revisions, and persistence integration tests.

### Step 3: Coordinator and cleanup state machine

Implement scheduling and one-experiment coordination with injected fakes, durability boundaries, preflight, injection, active verification, expiry, cancellation, cleanup retries, final verification, and strict outcomes. Use only the test synthetic scenario.

### Step 4: Supervisor, observation timeline, and reconciliation

Integrate the coordinator into a background supervisor, leases, persisted observations, control requests, signal handling, and restart reconciliation for every non-terminal state. Prove execution is independent from the scheduling CLI.

### Step 5: CLI, health, container, and operations

Add catalog, run, status, history, abort, and reconcile adapters; database migration commands; supervisor-aware local health; persistent deployment behavior; shutdown grace; and operator documentation. Keep the production catalog empty.

### Step 6: Phase 3 acceptance

Run the full domain, persistence, coordinator, restart, CLI, package, helper, Compose, and container matrix. Audit schemas, records, logs, images, and repository contents for secrets and operational target data. Complete acceptance evidence without contacting a real target.

## 17. Acceptance criteria

Update an item to `[x]` only when concrete evidence exists.

### Lifecycle safety

- [ ] Transition policy rejects every unapproved edge and terminal mutation.
- [ ] Injection cannot begin until durable state, preflight, and before observation succeed.
- [ ] Partial or uncertain injection always converges on cleanup.
- [ ] Expiry and cancellation are explicit, durable, and cannot produce false success.
- [ ] Cleanup is retry-safe, verified, and escalates exhausted uncertainty to operator attention.

### Persistence and concurrency

- [ ] Alembic migrations create a compatible SQLite schema on persistent storage.
- [ ] Database constraints enforce one non-terminal experiment per target.
- [ ] Transactions and optimistic revisions prevent duplicate claims and transitions.
- [ ] Audit transitions, attempts, observations, and requests are ordered and append-only through repositories.
- [ ] Database files and records contain no secrets, raw outputs, or unbounded evidence.

### Restart and supervision

- [ ] Experiment execution belongs to the supervised agent, not the CLI process.
- [ ] Every non-terminal state has a tested deterministic restart path.
- [ ] Uncertain mutating states never invoke injection again after restart.
- [ ] Graceful shutdown prioritizes cleanup; forced termination remains reconcilable.
- [ ] Lease loss cannot allow two runners to make forward progress.

### Observation and outcomes

- [ ] Before, during, and after observations are bounded and persisted.
- [ ] An unhealthy baseline prevents injection.
- [ ] Observation failure never disables expiry or cleanup.
- [ ] Passed, cancelled, failed, and operator-attention outcomes are distinguishable and justified by audit evidence.
- [ ] Local health remains distinct from target and website health.

### CLI, container, and documentation

- [ ] Production scenario catalog is empty and cannot load scenarios dynamically.
- [ ] CLI human and JSON contracts and exit codes are tested and documented.
- [ ] SQLite history survives container recreation under existing hardening restrictions.
- [ ] Schema upgrade, backup, abort, reconciliation, cleanup failure, and operator-attention runbooks are documented.
- [ ] All Python, migration, helper, image, Compose, and container gates pass without a real target.
- [ ] Repository contains no operational credential, target identity, database, or runtime data.
- [ ] Working tree is clean after the Phase 3 completion commit.

## 18. Documentation requirements

Update the README and operations guidance during implementation with:

- lifecycle state meanings and transition reasons;
- difference between scheduling and supervised execution;
- duration and hard-limit settings;
- scenario catalog and why it is empty in Phase 3;
- database location, permissions, schema upgrade, compatible backup, and recovery;
- status, history, abort, and reconcile examples;
- cleanup retry and operator-attention handling;
- restart and shutdown behavior;
- observation phase semantics;
- local health versus target preflight versus experiment observation; and
- explicit confirmation that Phase 3 itself contains no production fault injection.

## 19. Risks, assumptions, and deferred decisions

### Risks

- A crash between a target-side mutation and cleanup-context persistence creates uncertainty. Immutable experiment identity, idempotent scenario operations, cleanup-first reconciliation, and operator attention are mandatory defenses.
- SQLite supports the initial single-supervisor deployment, not horizontal replicas.
- Wall-clock changes can affect restart deadline evaluation; persisted expiry may never be extended automatically.
- Cleanup can fail because the target is unavailable or unverifiable. The engine must preserve this as operator attention rather than fabricate recovery.
- Excessive observation frequency can grow the database. Duration, interval, and record counts are bounded.
- A database on unreliable or network-mounted storage may violate SQLite assumptions. Support only documented local persistent storage in Phase 3.

### Assumptions

- Phase 2 secure target access remains unchanged and available to future scenarios.
- One container process supervises one configured development target.
- The persistent volume supports SQLite locking, atomic rename, fsync, and ordinary POSIX permissions.
- Operators can perform an explicit migration and consistent backup before upgrades.
- Scenario-specific target-side timeouts will provide an additional safety layer beginning in Phase 4.

### Deferred decisions

- Apache stop helper operations and real injection: Phase 4.
- CPU workload identity and cleanup: Phase 5.
- Dedicated disk test storage and allocation cleanup: Phase 6.
- Broader recovery drills and release hardening: Phase 7.
- Network database, multiple supervisors, API authorization, and remote scheduling: Phase 8 or later.
- Dashboard visualization: Phase 9.
- Independent remedy evaluation: Phase 10.

## 20. Approval to begin implementation

Acceptance of this specification authorizes repository implementation, migrations, local SQLite tests, fake scenario execution, and isolated container tests only. It does not authorize a real target connection, target provisioning, new `sudoers` permissions, or any disruptive action. Implementation begins only after this specification is reviewed and committed.
