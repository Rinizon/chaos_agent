# Remaining Local Work Specification

## 1. Purpose

This specification separates work that can be completed safely inside the repository from work that requires operator-controlled infrastructure, credentials, Docker Desktop access, an approved development target, or an independent remedy system.

No real-target experiment, target provisioning, privilege change, public API exposure, or release publication is authorized by this document.

## 2. Repository work the agent can complete

### 2.1 Production supervisor wiring

Integrate the durable supervisor into `chaos agent` so the long-running process:

- opens the configured local SQLite database;
- validates schema compatibility before work begins;
- constructs the closed scenario registry and fixed adapter dependencies;
- claims and renews leases;
- processes scheduled experiments independently of the CLI or HTTP request;
- performs cleanup-first restart reconciliation; and
- shuts down gracefully with the documented cleanup grace period.

The runtime must remain local-only for health reporting and must never silently start a target action without a durable scheduled experiment and successful preflight.

### 2.2 Production scenario adapter completion

Implement typed production control adapters that connect the three reviewed scenarios to the closed `RemoteTransport` operation set. The adapters must:

- pass only enum operations to OpenSSH;
- validate response types and target identity;
- enforce scenario-specific duration and parameter limits;
- preserve sanitized cleanup context;
- support bounded timeouts and cancellation; and
- never expose arbitrary commands, paths, PIDs, service names, or SSH options.

Add unit and integration tests using fake transport and observer implementations. Do not connect to a real target during this work.

### 2.3 Complete lifecycle observation wiring

Connect before, during, and after HTTP/resource observations to the coordinator and persistence layer. Verify bounded intervals, bounded record counts, sanitized failure categories, and cleanup priority when observation fails.

### 2.4 Target protocol hardening

Complete local contract coverage for all approved helper operations:

- Apache stop/start ownership and post-action verification;
- CPU workload identity, quota, reserve enforcement, non-root execution, and process-group cleanup;
- dedicated disk-storage marker validation, filesystem identity, allocation parameters, free-space reserve, partial allocation, and artifact ownership.

Update disposable fixtures and sudoers tests without broadening privileges. Any design that cannot prove ownership or reserve compliance must remain refused.

### 2.5 API completion

Extend the FastAPI adapter with:

- readiness reporting;
- detailed status and bounded history endpoints;
- authenticated abort and reconciliation endpoints;
- request IDs and stable error envelopes;
- idempotency keys for experiment creation;
- explicit role/permission boundaries;
- bounded request, response, pagination, retry, and timeout limits; and
- deployment configuration for TLS/reverse proxy, CORS, CSRF, CSP, and secure headers.

API handlers must enqueue durable requests and never execute target operations directly.

### 2.6 Dashboard completion

Extend the dashboard with:

- separate local, supervisor, target, website, and experiment health views;
- complete lifecycle timelines;
- bounded observations and audit history;
- abort and reconciliation controls;
- stale/degraded/operator-attention states;
- session expiry and reauthentication behavior;
- accessibility and responsive-layout tests; and
- safe production asset and browser security configuration.

The browser must use only the authenticated API and must not receive hidden cleanup context or target credentials.

### 2.7 Integration outbox completion

Wire lifecycle transitions and observations to the sanitized integration outbox. Add:

- durable event creation;
- per-experiment sequence metadata;
- bounded retention and queue limits;
- delivery retry state;
- authenticated, audited replay that cannot mutate targets; and
- tests for duplicate, delayed, missing, out-of-order, oversized, and unknown-version events.

Do not add a remedy callback or allow remedy input to reach target operations.

### 2.8 Documentation and release evidence

Update implementation specifications with evidence only after tests pass. Add operator runbooks for local deployment, schema migration, backup/restore, supervisor restart, API security, dashboard deployment, outbox attention, and release rollback.

Add deterministic local acceptance scripts for Python, migrations, helper contracts, API, dashboard assets, artifact scanning, and package/image checks.

## 3. Work requiring operator action

The following cannot be safely completed by repository-only changes:

- repair Docker Desktop/Buildx permissions and run container smoke tests;
- provision the isolated Linux development target;
- independently verify and install the target SSH host fingerprint;
- generate and mount the dedicated SSH key and known-hosts files;
- install and review target helper, dispatcher, marker, and sudoers files;
- create and verify dedicated test storage;
- supply runtime authentication secrets and TLS/reverse-proxy configuration;
- approve network exposure for the API/dashboard;
- authorize a real-target preflight;
- authorize and supervise real Apache, CPU, or disk experiments;
- provide an independent remedy system or remedy test double; and
- independently validate recovery and remedy attribution.

Operator actions must use reviewed artifacts and must not bypass strict host-key checking, target identity validation, reserve policy, or narrow sudo privileges.

## 4. Completion order

Repository work should proceed in this order:

1. Supervisor/runtime wiring and schema refusal.
2. Typed scenario control adapters and lifecycle observation wiring.
3. Local helper, persistence, restart, cleanup, and concurrency tests.
4. API completeness and security controls.
5. Dashboard timeline and degraded-state behavior.
6. Outbox publication, retry, retention, and replay controls.
7. Documentation and release evidence.
8. Operator-controlled container and real-target validation.

Do not begin real-target validation until the first seven repository stages pass and the relevant acceptance criteria are marked with evidence.

## 5. Acceptance criteria

- [ ] `chaos agent` supervises scheduled experiments and reconciles interrupted work.
- [ ] All three scenarios use production typed adapters with bounded, ownership-safe operations.
- [ ] Before, during, and after observations are persisted and do not disable cleanup.
- [ ] CPU and disk scenarios enforce their documented reserve and ownership policies.
- [ ] API status, control, readiness, idempotency, authorization, and security contracts are complete.
- [ ] Dashboard timeline, degraded-state, accessibility, and session behavior are complete.
- [ ] Lifecycle events populate a bounded, retryable, sanitized outbox.
- [ ] Local unit, integration, migration, API, dashboard, artifact, and package gates pass.
- [ ] Docker validation is either completed by the operator or explicitly recorded as blocked.
- [ ] Real-target validation is completed only after explicit operator approval.
- [ ] Independent remedy validation is completed separately from Chaos Agent cleanup.

## 6. Approval boundary

This specification authorizes planning and repository-only implementation of the listed local work. It does not authorize target access, privilege changes, public network exposure, disruptive experiments, remedy actions, or release publication.
