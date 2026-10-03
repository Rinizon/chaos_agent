# Completion Specification: Phases 1–10

## Status

In progress. This document is the authoritative execution checklist for completing the repository work identified by the 2026-10-02 audit. A checkbox may be marked complete only after implementation, automated verification, documentation, and a focused commit exist.

Operator-controlled validation is tracked separately and must never be inferred from local tests.

## Goal

Deliver a safety-focused Chaos Agent whose CLI, supervised lifecycle, three approved scenarios, API, dashboard, and independent integration stream share one typed application core and satisfy the phase specifications without arbitrary remote execution or remediation behavior.

## Non-negotiable boundaries

- No real target access, target provisioning, privilege changes, public exposure, disruptive test, release publication, or remedy action without explicit operator authorization.
- Only `apache-stop`, `cpu-pressure`, and `disk-pressure` may enter the production catalog.
- Every experiment is duration-bounded, durably scheduled, positively identifies the target, observes externally visible health, and converges on retry-safe cleanup or operator attention.
- Remote operations use a closed protocol with typed, bounded data; no shell fragments, caller-selected commands, arbitrary paths, or caller-selected PIDs.
- Cleanup removes or reverses only experiment-owned effects. It is safety behavior, not remediation.
- Runtime schema compatibility is explicit; application startup never silently manufactures or upgrades a production database.
- Secrets and raw diagnostics never enter logs, API responses, browser assets, audit records, or integration events.

## Step 1 — Re-establish the Phase 1–2 quality baseline

- [x] Apply repository formatting and keep Ruff lint clean. Evidence: commit `83c97f9`; Ruff lint and format checks pass.
- [x] Preserve strict mypy success and package builds. Evidence: strict mypy and source/wheel build passed on 2026-10-02.
- [ ] Preserve Phase 1 local health semantics and Phase 2 read-only preflight restrictions.
- [x] Add a deterministic local acceptance command or script covering tests, lint, format, typing, build, migrations, helper contracts, and secret/artifact checks. Evidence: `scripts/release-check.sh` passed in commit `b210241`.
- [ ] Update README language so implemented, accepted, deferred, and operator-blocked work are distinguishable.

Evidence: full local quality matrix, clean focused commit, and current documentation.

## Step 2 — Complete the Phase 3 lifecycle engine

- [x] Keep a successfully injected experiment `active` until expiry or cancellation. Evidence: `test_successful_injection_remains_active_before_expiry` in commit `83c97f9`.
- [x] Reconcile uncertain `injecting` state cleanup-first without treating every active experiment as uncertain. Evidence: coordinator and supervisor tests in commit `83c97f9`.
- [ ] Process cancellation in every eligible non-terminal state and preserve cancelled attribution through cleanup.
- [ ] Renew and fence leases while work is owned; never release another supervisor's lease. Claim fencing and pre-execution renewal are complete in commit `9a7f913`; periodic renewal during a long operation remains open.
- [x] Persist bounded before, during, and after external observations. Evidence: lifecycle observation tests in commit `2c2b65d`.
- [x] Ensure observation failure never blocks expiry, cancellation, or cleanup. Evidence: failure-path test in commit `2c2b65d`.
- [ ] Prioritize reconciliation and cleanup during graceful shutdown.
- [x] Require the exact supported Alembic revision at runtime and API/CLI database entry points. Evidence: revision acceptance/refusal tests in commit `9b44084`.
- [ ] Add deterministic tests for active duration, expiry, cancellation, partial injection, restart, lease loss, repeated cleanup, and shutdown.

Evidence: lifecycle tests, migration compatibility tests, local process smoke, and Phase 3 acceptance updates.

## Step 3 — Complete the Phase 4 Apache scenario

- [ ] Bind every response to the configured target identity and exact requested operation.
- [ ] Persist ownership evidence before the stopped service can be considered active.
- [ ] Observe the expected outage during the active interval.
- [ ] Start Apache only when stop ownership is proven.
- [ ] Verify Apache and external website recovery after cleanup.
- [ ] Cover refusal, timeout, partial stop, restart, cancellation, expiry, repeated cleanup, and cleanup failure.

Evidence: unit, helper, coordinator, and disposable-target tests plus Phase 4 acceptance updates.

## Step 4 — Complete the Phase 5 CPU scenario

- [ ] Extend the closed helper protocol with typed experiment ID, worker count, CPU quota, and duration fields.
- [ ] Run workloads under a dedicated non-root identity in an experiment-owned scope.
- [ ] Enforce conservative worker/quota limits and retain management capacity.
- [ ] Record ownership atomically and verify the complete process group before cleanup.
- [ ] Use a target-side deadline independent of the agent process.
- [ ] Stop only the owned workload, wait boundedly, and prove absence.
- [ ] Cover malformed input, partial start, stale ownership, PID reuse, timeout, restart, cancellation, and repeated cleanup.

Evidence: scenario, protocol, helper, and lifecycle tests plus Phase 5 acceptance updates.

## Step 5 — Complete the Phase 6 disk scenario

- [ ] Strictly validate a root-owned, non-writable, bounded dedicated-storage marker.
- [ ] Prove the approved location is not `/`, does not share the root filesystem, and is outside system, web, log, database, and control paths.
- [ ] Extend the closed protocol with typed experiment ID, allocation, chunk, and duration fields.
- [ ] Allocate real blocks in bounded chunks while continuously preserving the configured reserve.
- [ ] Persist an experiment-owned artifact record before mutation and handle partial allocation safely.
- [ ] Remove only the exact owned regular file without following links.
- [ ] Verify artifact absence, storage reserve, Apache, and website health after cleanup.
- [ ] Cover malformed markers, sparse/partial behavior, full-device errors, restart, cancellation, and repeated cleanup.

Evidence: scenario, protocol, helper, filesystem-fixture, and lifecycle tests plus Phase 6 acceptance updates.

## Step 6 — Complete Phase 7 MVP hardening

- [ ] Run the full scenario lifecycle matrix using fakes and disposable local fixtures.
- [ ] Test container/process restart, SSH interruption, stale lease, database backup/restore, cleanup exhaustion, and operator attention.
- [ ] Stabilize human and JSON CLI output and exit codes.
- [ ] Scan repository, build artifacts, logs, and database fixtures for secrets and operational target data.
- [ ] Complete deployment, migration, backup/restore, key rotation, abort, reconciliation, emergency, and rollback runbooks.
- [ ] Produce reproducible package artifacts and record Docker validation as passed or operator-blocked.

Evidence: acceptance script output, release notes, runbooks, reproducible artifacts, and Phase 7 acceptance updates.

## Step 7 — Complete Phase 8 API

- [ ] Reuse application services for catalog, preflight, scheduling, status, history, abort, and reconciliation.
- [ ] Add readiness distinct from local liveness and remote health.
- [ ] Add experiment detail, transitions, observations, attempts, and bounded pagination/filtering.
- [ ] Add durable idempotency keys, request/correlation IDs, stable error envelopes, and audit attribution.
- [ ] Add explicit viewer/operator roles and constant-time token validation.
- [ ] Add bounded request/response behavior, secure headers, explicit CORS/CSRF policy, and reverse-proxy/TLS deployment guidance.
- [ ] Prove API restarts cannot orphan experiments or execute target work in request handlers.

Evidence: security, contract, persistence, restart, and deployment tests plus Phase 8 acceptance updates.

## Step 8 — Complete Phase 9 dashboard

- [ ] Use only authenticated Phase 8 endpoints.
- [ ] Show local, supervisor, target, website, and experiment health separately.
- [ ] Provide validated launch confirmation and durable abort/reconcile requests.
- [ ] Render lifecycle transitions, observations, attempts, expiry, cleanup, final outcome, and operator attention.
- [ ] Handle stale data, API loss, session expiry, and reauthentication without unsafe retries.
- [ ] Prevent secrets, hidden cleanup context, and raw diagnostics from reaching browser assets.
- [ ] Pass keyboard, screen-reader, contrast, responsive-layout, CSP, and browser contract tests.

Evidence: component, accessibility, security, end-to-end, and deployment tests plus Phase 9 acceptance updates.

## Step 9 — Complete Phase 10 independent integration

- [ ] Publish sanitized lifecycle and observation events transactionally with state changes.
- [ ] Include per-experiment monotonic sequence, event ID, schema version, correlation ID, and bounded public evidence.
- [ ] Enforce queue/retention limits and explicit operator attention on exhaustion.
- [ ] Implement retry state and authenticated audited replay without any target-mutation path.
- [ ] Safely handle duplicate, delayed, missing, out-of-order, oversized, and unknown-version events.
- [ ] Document the independent judge contract and distinguish remedy action, chaos cleanup, and operator intervention.

Evidence: contract, sequencing, retention, replay, security, and failure-mode tests plus Phase 10 acceptance updates.

## Step 10 — Final local acceptance and operator handoff

- [ ] All repository-only criteria above are complete and committed.
- [ ] All Python, migration, helper, API, dashboard, artifact, and package gates pass from a clean checkout.
- [ ] Phase specifications and README contain current evidence without overstating external validation.
- [ ] Docker/container validation is passed by the operator or explicitly recorded as blocked.
- [ ] Guarded real-target Apache, CPU, and disk validation occurs only with explicit operator authorization.
- [ ] Independent remedy validation occurs separately and never counts Chaos Agent cleanup as remedy success.
- [ ] Working tree is clean and the release decision records every remaining external dependency.

## Completion policy

Repository implementation may complete Steps 1–9 locally. Step 10 remains incomplete while Docker access, an approved isolated target, runtime secrets/TLS, or an independent remedy system are unavailable. Those external dependencies are blockers to release approval, not permission to weaken safety checks or simulate acceptance evidence.
