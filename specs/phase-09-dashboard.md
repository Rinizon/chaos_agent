# Phase 9 Specification: Monitoring Dashboard

## 1. Purpose

Phase 9 adds a browser-based dashboard over the authenticated Phase 8 service API. It gives operators a clear view of local agent health, configured target and website observations, approved scenarios, experiment timelines, expiry, cleanup, and final outcomes.

The dashboard is an operator interface, not a second execution engine. It must not contain scenario logic, direct SSH access, target credentials, remediation logic, or arbitrary command controls.

## 2. Scope and responsibility

The dashboard may:

- display local agent and supervisor health;
- display configured target and website status as separate signals;
- list approved scenarios and their bounded public parameters;
- submit validated experiment requests through the Phase 8 API;
- show experiment status, transitions, observations, expiry, cleanup, and outcomes;
- request abort or reconciliation through the API; and
- identify operator-attention conditions with clear next actions.

The dashboard may not:

- connect directly to SSH, the target VM, SQLite, or target storage;
- accept arbitrary target hosts, commands, service names, paths, process IDs, or cleanup instructions;
- bypass API authentication or authorization;
- infer target health from a single browser request;
- poll so aggressively that it overwhelms the API or obscures safety state; or
- present chaos cleanup as remedy success.

## 3. Architecture

Use a static or separately served browser client over the authenticated Phase 8 API:

```text
browser dashboard
        -> authenticated API
        -> application services and supervisor
        -> persistence, observer, and target adapters
```

The dashboard must not duplicate lifecycle transitions, duration rules, scenario parameter validation, authorization, or cleanup decisions. The API remains authoritative for all state and actions.

The dashboard must tolerate API restarts, delayed responses, stale data, expired sessions, and partial outages. It must label cached or stale data clearly and must never imply that a failed refresh means the target is healthy or safe.

## 4. Authentication and session behavior

- Use the Phase 8 authentication and authorization mechanism; do not introduce a separate bypass.
- Do not store bearer tokens in URLs, local source files, browser logs, analytics payloads, or server-rendered HTML.
- If browser storage is used, document its threat model and prefer short-lived, secure, HttpOnly, same-site session handling through a trusted deployment boundary.
- Show generic authentication and authorization errors without exposing protected resource details.
- Expired or revoked sessions must stop mutating actions until reauthentication.
- Prevent cross-site request forgery for cookie-authenticated mutation requests.
- Do not trust identity or role values supplied by browser-controlled headers.

## 5. Dashboard views

### 5.1 Overview

Display:

- local agent health and heartbeat age;
- supervisor readiness and degraded state;
- database/schema readiness;
- configured target identity status;
- external website availability and latency; and
- active experiment summary, if any.

Local agent health, target preflight, website health, and experiment state must be visibly distinct. A healthy dashboard or API process must not be shown as proof that the target site is healthy.

### 5.2 Scenario catalog

For each approved scenario, show its stable name, version, description, capability summary, duration ceiling, and public parameter bounds. Forms must be generated from server-provided schemas or a tightly versioned client contract and must reject invalid values before submission.

Do not display hidden cleanup context, target command details, credentials, or unrestricted controls.

### 5.3 Launch flow

The launch flow must:

1. show the selected scenario and validated parameters;
2. state that the target is configured server-side;
3. display the mandatory duration and expiry;
4. require explicit operator confirmation;
5. submit an idempotent API request;
6. show that scheduling is not injection or success; and
7. link to the experiment timeline.

The UI must prevent accidental double submission and display the server’s idempotency result.

### 5.4 Experiment timeline

Show, in order:

- scheduling and actor;
- preflight and baseline observation;
- injection and effect verification;
- active interval and expiry countdown;
- during observations;
- abort or expiry request;
- cleanup attempts and verification;
- after observation; and
- final outcome.

Use distinct visual states for `planned`, `preflight`, `injecting`, `active`, `cancellation_requested`, `expired`, `cleaning_up`, `cleanup_failed`, `verifying`, `passed`, `cancelled`, `failed`, and `operator_attention`.

### 5.5 History and audit

Provide bounded, paginated history with filters for scenario, state, actor, and time range. Display sanitized evidence and observations only. Make it clear which records describe chaos injection, emergency cleanup, operator action, and independent recovery verification.

## 6. Controls and safety UX

- Abort is a durable request, not an immediate success claim.
- Reconcile is a durable request and must explain that the supervisor performs the work.
- Disable launch controls when readiness, target preflight, schema, or authentication state is unsafe.
- Keep abort and reconciliation available when appropriate during degraded target conditions.
- Require confirmation for abort and any future destructive operator action.
- Never hide `operator_attention`; place it prominently and explain that automatic safety cannot be confirmed.
- Show stale timestamps and refresh failures prominently.
- Avoid automatic refresh intervals below the documented API rate limit.
- Never make a browser navigation, tab close, or websocket disconnect cancel an experiment.

## 7. API interaction and limits

- Use only documented `/api/v1` endpoints.
- Propagate request IDs and display them in diagnostic details without exposing secrets.
- Use bounded request timeouts, exponential backoff, and a maximum retry count.
- Do not retry mutation requests without preserving the original idempotency key.
- Use pagination and bounded history windows.
- Treat unknown fields and unknown states as safe degraded states, not as permission to guess.
- Render server-provided text as text, not unsanitized HTML.

## 8. Security and deployment

- Serve the dashboard only over the documented TLS/reverse-proxy boundary.
- Apply a strict content-security policy, secure headers, frame protections, and appropriate same-site cookie policy.
- Do not embed secrets in JavaScript bundles, source maps, HTML, browser configuration, or static assets.
- Configure allowed API origins explicitly; do not use wildcard production CORS with credentials.
- Keep the dashboard’s deployment identity separate from target SSH identity.
- Do not expose the SQLite database, target storage, Docker socket, or SSH material to the browser or dashboard server.
- Ensure frontend error reporting and analytics redact experiment parameters, tokens, target identifiers where sensitive, and response bodies.

## 9. Accessibility and usability

- Provide keyboard navigation and visible focus states.
- Use text and status labels in addition to color.
- Make countdowns and refresh updates understandable to screen readers without excessive announcements.
- Provide responsive layouts for operator laptop and tablet sizes.
- Keep critical safety state visible without requiring hover or animation.
- Support reduced motion and clear error recovery.

## 10. Testing requirements

### 10.1 Component and contract tests

Cover:

- scenario form bounds and unknown-parameter refusal;
- authenticated API calls and safe error handling;
- idempotent launch behavior and duplicate-submit prevention;
- all lifecycle states and unknown-state degradation;
- stale data, refresh failure, API restart, and expired session behavior;
- pagination, filters, bounded retries, and request IDs; and
- safe rendering of server-provided text.

### 10.2 Security tests

Verify:

- no token or secret appears in URLs, bundles, logs, analytics, or rendered markup;
- unauthorized users cannot launch, abort, reconcile, or view protected data;
- CSRF protections work for cookie-authenticated mutations;
- CORS, CSP, frame, and secure-cookie policies are enforced;
- browser-controlled headers cannot spoof actor or role;
- target commands and hidden cleanup context never reach the browser; and
- XSS payloads in scenario descriptions, actor names, messages, and evidence render inertly.

### 10.3 End-to-end tests

Use a fake API and deterministic lifecycle data to exercise launch, timeline updates, expiry, cleanup failure, operator attention, abort, reconciliation, and recovery views. Verify browser disconnects do not alter experiment state.

### 10.4 Deployment tests

Test static asset build, reverse-proxy headers, TLS configuration, API origin restrictions, cache behavior, service restart, stale frontend/API version compatibility, and absence of credentials or target data in release artifacts.

## 11. Documentation requirements

Document:

- dashboard deployment and TLS boundary;
- authentication, roles, session expiry, and logout;
- scenario launch confirmation and idempotency;
- refresh, stale-data, and degraded-state semantics;
- abort, reconciliation, cleanup failure, and operator-attention behavior;
- audit interpretation and chaos/remedy boundaries;
- API compatibility and frontend upgrade procedure; and
- rollback and secret-rotation procedures.

Do not document a direct target-access workaround or any arbitrary command control.

## 12. Acceptance criteria

Update each item only after concrete evidence exists:

- [ ] Dashboard uses the authenticated Phase 8 API and contains no direct target or persistence adapter.
- [ ] Authentication, authorization, session expiry, CSRF, CORS, CSP, and secure-header controls are enforced.
- [ ] Scenario forms expose only reviewed bounded parameters and prevent duplicate submissions.
- [ ] Overview clearly separates local agent, supervisor, target, website, and experiment state.
- [ ] Timeline represents every lifecycle state, expiry, cleanup attempt, observation, and final outcome.
- [ ] Abort and reconciliation are presented as durable requests, not completed actions.
- [ ] Operator-attention and stale/degraded states are prominent and never hidden.
- [ ] History is bounded, paginated, filterable, and sanitized.
- [ ] Browser disconnects, API restarts, stale data, and expired sessions cannot trigger unsafe actions.
- [ ] Tokens, secrets, raw output, hidden cleanup context, and arbitrary commands never reach browser artifacts or logs.
- [ ] Accessibility and responsive-layout requirements pass automated and manual checks.
- [ ] Component, security, contract, end-to-end, and deployment tests pass.
- [ ] Documentation and operational runbooks are complete.
- [ ] No new chaos scenario, autonomous selection, remedy logic, or direct SSH capability is included.
- [ ] Working tree is clean after the Phase 9 implementation commit.

## 13. Approval to begin implementation

Creating this specification does not authorize dashboard implementation, browser exposure, authentication changes, target access, disruptive experiments, or release publication. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
