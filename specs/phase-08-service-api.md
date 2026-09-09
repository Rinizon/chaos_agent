# Phase 8 Specification: Service API

## 1. Purpose

Phase 8 exposes the proven Chaos Agent application services through an authenticated API. The API must reuse the existing domain, persistence, observation, transport, scenario, and supervisor boundaries rather than duplicating CLI business logic.

The service API is a control-plane interface. It does not broaden target access, expose arbitrary remote execution, add autonomous scenario selection, or implement remedy behavior.

## 2. Scope and responsibility

The API may:

- list reviewed scenarios and their public parameter schemas;
- run preflight and return sanitized results;
- schedule approved experiments;
- retrieve experiment status, history, transitions, observations, and outcomes;
- request cancellation or reconciliation; and
- report local agent health separately from target and website health.

The API may not:

- accept arbitrary target hosts, SSH options, commands, paths, process IDs, service names, or cleanup instructions;
- execute target operations in the request handler;
- bypass scenario validation or lifecycle state transitions;
- expose secrets, raw remote output, private cleanup context, response bodies, or credentials; or
- claim emergency chaos cleanup as remedy success.

## 3. Service architecture

Use a thin FastAPI adapter over existing application services:

```text
authenticated HTTP request
        -> API validation and authorization
        -> application service
        -> domain policy / scenario registry
        -> repository, supervisor, observer, and transport adapters
```

The API process may enqueue durable requests, but the supervisor owns experiment execution, expiry, observations, cleanup, reconciliation, and final state. Request handlers must remain bounded and must not hold database transactions across SSH, HTTP, waits, or target actions.

The supervisor must be a separately managed background component or an explicitly supervised worker within the service process. Its lifecycle must be independent of any individual HTTP connection.

## 4. Authentication and authorization

### 4.1 Authentication

Require a documented production authentication mechanism before serving non-health endpoints. The initial implementation may use a validated bearer-token adapter backed by runtime-injected secret material, provided that:

- tokens are never stored in the repository, image, database, or logs;
- comparison is constant-time where applicable;
- missing, malformed, expired, and invalid credentials produce safe errors;
- health and readiness exposure is intentionally documented; and
- authentication configuration fails closed.

Do not accept credentials in URLs, query strings, experiment parameters, or target configuration fields.

### 4.2 Authorization

Attribute every mutating request to an authenticated actor and enforce explicit permissions:

- read-only operators may view scenarios, status, history, observations, and health;
- experiment operators may run approved scenarios, abort experiments, and request reconciliation;
- administrators may manage service configuration only through the deployment and secret-management process, not through target-action endpoints.

The first version must not provide a privilege that means unrestricted target control. Authorization failures must not reveal whether a hidden resource exists beyond the documented identifier behavior.

## 5. API contract

Use versioned routes under `/api/v1`.

### 5.1 Health and readiness

```text
GET /health
GET /ready
```

Health reports local process, heartbeat, storage, schema, and supervisor state. It must not claim the target website is healthy. Readiness fails closed when configuration, schema, persistent storage, or required supervisor ownership is unsafe.

### 5.2 Scenarios and preflight

```text
GET  /api/v1/scenarios
POST /api/v1/preflight
```

Scenario responses expose stable names, versions, descriptions, capability summaries, duration limits, and safe parameter schemas. They do not expose hidden cleanup context or target command details.

Preflight accepts no arbitrary target override. It uses the configured target and returns sanitized, bounded checks and stable refusal categories.

### 5.3 Experiments

```text
POST /api/v1/experiments
GET  /api/v1/experiments
GET  /api/v1/experiments/{experiment_id}
POST /api/v1/experiments/{experiment_id}/abort
POST /api/v1/experiments/{experiment_id}/reconcile
```

The create request contains only:

- approved scenario name and version;
- strictly validated scenario parameters;
- requested duration within global and scenario bounds; and
- optional client idempotency key.

Target identity, host, service names, SSH settings, cleanup context, and remote commands are server-owned configuration and are never request fields.

Successful creation returns `202 Accepted` with the experiment ID, scheduled state, actor attribution, expiry, and a status URL. It does not imply preflight success, injection, impact, cleanup, or recovery.

List and detail responses return bounded public experiment data, state transitions, sanitized action evidence, observations, timestamps, final outcome, and operator-attention reason when applicable. They must not return private cleanup values or raw adapter output.

### 5.4 Error contract

Use one versioned error envelope:

```json
{
  "schema_version": 1,
  "category": "scenario_unavailable",
  "message": "Scenario is unavailable.",
  "request_id": "..."
}
```

Categories must be stable and safe. Do not include stack traces, SQL, SSH command lines, target paths, response bodies, credentials, or rejected secret values.

## 6. Idempotency and concurrency

- Require an idempotency key for experiment creation or generate a server-side request identity before durable scheduling.
- Repeating the same authorized create request must return the existing experiment identity without creating a duplicate.
- Idempotency keys must be scoped to actor and operation, bounded in length, and persisted without secrets.
- Preserve one-active-experiment-per-target protection in the repository and database.
- Use optimistic revisions and leases to prevent duplicate supervisor progress.
- Concurrent abort, expiry, cleanup, and reconciliation requests must resolve through durable state transitions; no request handler may perform a competing cleanup.

## 7. Background execution and restart

The supervisor must:

- claim scheduled work with a durable lease;
- renew leases while external operations are active;
- prioritize expiry and cleanup over observation or new work;
- reconcile every non-terminal state after restart;
- never reinject an uncertain or previously active experiment; and
- degrade readiness or health when operator attention is required without creating a restart loop.

The API must remain responsive when a target is slow or unavailable. Bounded request timeouts apply to enqueue/read operations; long-running experiment work is never tied to an HTTP connection.

Graceful shutdown must stop accepting new work, allow the documented cleanup grace period, persist state, and leave forced-termination cases recoverable through reconciliation.

## 8. Audit, observability, and limits

Record for each request:

- request ID and authenticated actor;
- operation and resource identifier;
- authorization result;
- idempotency result;
- bounded outcome category; and
- timestamp and correlation identifiers.

Do not log authorization tokens, cookies, complete headers, request bodies containing sensitive values, raw target output, or private cleanup context.

Apply bounded request body size, parameter document size, list limits, pagination limits, response size, header limits, timeout, and rate limits. Protect the API from repeated scheduling, abort, preflight, and status polling without making safety operations impossible.

## 9. Security and deployment requirements

- Bind only to the documented control-plane interface; do not expose the target VM or SSH service through the API.
- Run as the existing non-root container user unless a separately reviewed deployment requires otherwise.
- Retain read-only root, dropped capabilities, no-new-privileges, no Docker socket, and read-only secret mounts.
- Inject authentication secrets at runtime and rotate them without storing them in the image or database.
- Use a documented reverse proxy or TLS boundary for deployment; do not implement insecure plaintext production authentication.
- Configure trusted proxy behavior explicitly; never trust caller-supplied forwarded identity headers by default.
- Return generic authentication and authorization failures without leaking protected resource details.

## 10. Testing requirements

### 10.1 API contract tests

Cover:

- route status codes and versioned response schemas;
- authentication success, missing, malformed, expired, and invalid credentials;
- authorization for each role and operation;
- request size, parameter, duration, and pagination bounds;
- unknown routes and methods;
- safe error redaction;
- scenario listing and unavailable-scenario refusal;
- preflight delegation; and
- health/readiness separation from target health.

### 10.2 Lifecycle and concurrency tests

Use fake repositories, clocks, target transport, observer, scenario controls, and leases to prove:

- create requests enqueue but do not execute target actions;
- idempotent retries do not duplicate experiments;
- one-active-experiment protection holds under concurrent requests;
- abort and reconcile are durable requests;
- API disconnection does not stop execution or cleanup;
- supervisor restart reconciles every non-terminal state;
- lease loss prevents duplicate forward progress; and
- cleanup and operator attention remain visible through the API.

### 10.3 Security tests

Verify that tokens, secrets, private cleanup context, raw SSH output, target paths, and arbitrary commands are absent from logs, database records, errors, and responses. Test forwarded-header spoofing, oversized requests, repeated idempotency keys, unauthorized resource access, and malformed database records.

### 10.4 Integration and deployment tests

Test migrations, persistent storage, service startup, graceful shutdown, container health, readiness degradation, reverse-proxy configuration, and API process restart without a real target. Real-target validation remains separately guarded and is not required for default tests.

## 11. Documentation requirements

Document:

- endpoint and error contracts;
- authentication and role configuration;
- idempotency behavior;
- supervisor and shutdown behavior;
- health/readiness semantics;
- rate, size, timeout, and pagination limits;
- audit and redaction policy;
- TLS/reverse-proxy deployment;
- secret rotation;
- backup, migration, and rollback; and
- the boundary between chaos cleanup and remedy behavior.

Do not document or expose a generic remote shell, arbitrary target override, or privilege-broadening workaround.

## 12. Acceptance criteria

Update each item only after concrete evidence exists:

- [ ] FastAPI routes reuse application services without duplicating lifecycle logic.
- [ ] Authentication is runtime-configured, fail-closed, and absent from logs, images, and persistence.
- [ ] Authorization roles and actor attribution are enforced for every mutating operation.
- [ ] Scenario and parameter schemas expose only reviewed, bounded capabilities.
- [ ] API requests cannot supply arbitrary target, SSH, service, process, path, or command values.
- [ ] Experiment creation is asynchronous, durable, idempotent, and returns no false success.
- [ ] One-active-experiment, optimistic revision, and lease protections hold under concurrency.
- [ ] Supervisor execution, expiry, cleanup, and reconciliation are independent of HTTP connections.
- [ ] Health/readiness output distinguishes local agent, supervisor, target, and website state.
- [ ] Responses, errors, logs, and audit records are bounded and secret-safe.
- [ ] Restart, shutdown, timeout, transport failure, and operator-attention behavior are tested.
- [ ] Container and reverse-proxy deployment retain Phase 7 hardening requirements.
- [ ] API, security, persistence, migration, integration, and deployment tests pass.
- [ ] Documentation and operational runbooks are complete.
- [ ] No dashboard, autonomous scenario selection, arbitrary remote execution, or remedy logic is included.
- [ ] Working tree is clean after the Phase 8 implementation commit.

## 13. Approval to begin implementation

Creating this specification does not authorize API implementation, authentication-secret provisioning, network exposure, target access, disruptive experiments, or release publication. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
