# Chaos Agent Status Report

**Audit date:** 2026-10-02  
**Audited revision:** `3d53793` (`main`, matching `origin/main` at audit start)  
**Overall status:** Not release-ready. Phase 1 and Phase 2 have historical completion evidence; Phase 3 remains incomplete; Phases 4–10 contain partial implementations or scaffolding but do not meet their acceptance criteria.

## Executive summary

The repository has a sound architectural direction: typed domain contracts, a transport boundary, strict target identity checks, SQLite-backed experiment records, a Typer CLI, and container artifacts. The current test suite is green, strict type checking passes, lint rules pass, and source/wheel builds succeed.

Those checks do not establish that the current product works end to end. Several production paths are either incomplete or unsafe to approve:

1. An experiment that reaches `active` is immediately transitioned to cleanup, even when its expiry is still in the future.
2. CPU and disk operations are advertised by the dispatcher and application but rejected by the target helper's top-level operation allowlist.
3. Production scenario control discards scenario parameters and experiment identity, so CPU worker/load limits and disk allocation sizes cannot reach the target helper.
4. Before/during/after observations are not wired into experiment execution or persistence.
5. Runtime startup creates tables directly rather than checking and applying the explicit migration contract.
6. The API, dashboard, and integration outbox are early adapters, not completed Phase 8–10 products.
7. The required formatting gate currently fails on 12 files.

No real target was contacted and no disruptive operation was run during this audit.

## Verification performed

| Check | Result | Evidence |
| --- | --- | --- |
| Repository state at start | Pass | Clean `main`, aligned with `origin/main` |
| Locked dependency sync | Pass | `uv sync --all-groups --locked` completed |
| Unit/smoke test suite | Pass with warning | 220 passed; one Starlette/httpx deprecation warning |
| Ruff lint | Pass | All lint checks passed |
| Ruff formatting | **Fail** | 12 files would be reformatted |
| Strict mypy | Pass | No issues in 35 source files |
| Source and wheel build | Pass | Both artifacts built successfully |
| Docker/container smoke | Not run | Requires operator-controlled Docker access; already documented as pending |
| Real-target validation | Not run | Requires explicit operator approval and provisioned isolated target |

The test suite has meaningful coverage of configuration, preflight, transport restrictions, lifecycle contracts, persistence, Apache scenario basics, CLI behavior, and local health. It has little or no direct coverage of the production scenario adapter, CPU/disk scenario behavior, helper execution for CPU/disk, active-duration supervision, lifecycle observation wiring, API control paths, dashboard behavior, or outbox delivery semantics.

## Completion audit by phase

| Phase | Assessment | Rationale |
| --- | --- | --- |
| 1 — Foundation | Historically complete; partially reverified | Package, CLI foundation, typing, tests, and build remain healthy. Formatting currently fails and container smoke was not rerun, so all original gates are not currently green. |
| 2 — Secure target access | Historically complete; partially reverified | Read-only preflight, identity contracts, SSH restrictions, and helper tests exist. No live target or container verification was performed in this audit. |
| 3 — Experiment engine | **Incomplete** | Its specification says Steps 1–5 complete and leaves the all-gates acceptance item open. Current production supervision cleans active experiments immediately, does not continuously renew leases, lacks lifecycle observations, and bypasses schema compatibility checks with `create_all`. |
| 4 — Apache stop | Partial prototype | Typed scenario and helper operations exist, but the full lifecycle, observation, expiry, restart, migration, container, and guarded real-target criteria are unchecked. |
| 5 — CPU pressure | **Not complete / non-operational** | Scenario code exists, but helper allowlisting rejects CPU operations; parameters are not passed to the helper; workload percentage and worker count are not enforced; the helper starts one unrestricted `yes` process as root; dedicated tests are absent. |
| 6 — Disk pressure | **Not complete / non-operational** | Scenario code exists, but helper allowlisting rejects disk operations; requested allocation/chunk parameters are ignored; storage-marker ownership/mode/filesystem validation is insufficient; dedicated tests are absent. |
| 7 — MVP hardening | Not complete | Release notes explicitly withhold approval. The formatting gate fails, container/real-target evidence is missing, and Phases 3–6 are not complete. |
| 8 — Service API | Scaffold only | Bearer authentication, catalog, create/list, and event-list endpoints exist. Required readiness, status detail, abort/reconcile, idempotency, roles, stable errors, pagination, and deployment security are absent. |
| 9 — Dashboard | Scaffold only | A small inline HTML page can launch and list experiments. Required health separation, timelines, audit/observations, abort/reconcile, stale states, session handling, accessibility, responsive tests, and security hardening are absent. |
| 10 — Remedy integration | Contract/outbox scaffold only | A model, table, repository, and read endpoint exist. Lifecycle publication, sequencing, retention, retries, delivery, replay controls, and failure-mode tests are absent. |

## Release-blocking findings

### P0 — Active duration is not honored

`ExperimentCoordinator.run_once()` correctly checks whether an active experiment is expired, but then includes every `active` experiment in the unconditional cleanup set. A newly injected experiment therefore transitions to cleanup in the same call instead of remaining active until its deadline. `Supervisor.reconcile()` also invokes the coordinator for every non-terminal row on every tick.

**Impact:** The central time-bounded experiment lifecycle is incorrect. The product cannot demonstrate the requested active interval or during-experiment observations.

### P0 — CPU and disk target operations cannot execute

The dispatcher, sudoers file, domain enum, and response builder mention CPU and disk operations, but `ops/target/target-helper` accepts only the Phase 2 and Apache operation names in its `OPERATIONS` set. Its `main()` rejects every CPU or disk command before dispatch.

**Impact:** Two of the three claimed MVP scenarios are non-operational on a target.

### P0 — Scenario parameters do not cross the transport boundary

`SshScenarioControl` receives typed CPU/disk parameters but calls `OpenSshTransport.execute()` with only an enum operation. The target helper consequently hard-codes one `yes` process and a maximum 256 MiB sparse truncation. Experiment ID, worker count, target CPU percentage, requested allocation, and chunk size never reach the helper.

**Impact:** Validated user parameters are not enforced by the target operation, ownership is not experiment-specific for CPU, and audit records can disagree with the actual fault.

### P0 — CPU helper violates the documented safety design

The helper launches `/usr/bin/yes` directly while running as root, does not cap CPU quota, ignores worker count and target percentage, stores only a PID, and sends a signal without a bounded wait or process-group verification.

**Impact:** CPU pressure does not preserve the promised management reserve and does not meet the non-root, bounded, ownership-safe requirements.

### P0 — Disk helper does not prove dedicated-storage safety

The storage marker is parsed without the same root ownership, mode, size, schema, and symlink controls used for the target marker. The helper does not prove that the path is a distinct non-root filesystem, does not bind artifacts to an experiment ID, ignores requested allocation, and uses `truncate`, which may create a sparse file without consuming the intended capacity.

**Impact:** The dedicated-storage and observable-pressure guarantees are not established.

### P1 — Lifecycle observations are not wired

The persistence repository can record a site observation, but the coordinator never calls an observer or records before/during/after samples. Production preflight performs one HTTP check only.

**Impact:** Required experiment evidence is absent, and Phase 3 plus every scenario definition of done remains unmet.

### P1 — Production schema handling bypasses migration safety

The long-running runtime and API call `Base.metadata.create_all()`. They do not verify the Alembic revision, refuse incompatible schemas, or perform the documented upgrade workflow.

**Impact:** Startup can run against an unexpected schema without the promised compatibility guard.

### P1 — Lease and shutdown behavior is incomplete

The supervisor can claim and release a lease, but does not renew it while work is active. Execution is synchronous inside a heartbeat tick, and graceful shutdown does not explicitly prioritize active cleanup within a bounded grace period.

**Impact:** Long operations can lose ownership, heartbeat updates can pause, and restart/concurrency guarantees are not proven.

### P1 — API and dashboard controls are incomplete

The API lacks experiment-detail, transition/observation history, abort, reconcile, readiness, roles, request IDs, stable error envelopes, creation idempotency, and deployment security controls. The dashboard uses a browser-entered bearer token and has no abort/reconcile or detailed monitoring workflow.

**Impact:** Phases 8 and 9 should not be represented as completed or production-safe.

### P1 — Outbox is not connected to lifecycle events

The outbox table and read endpoint exist, but coordinator transitions and observations do not publish events. Delivery state is not advanced, retried, retained, or replayed through an audited contract.

**Impact:** Phase 10 currently provides no functioning integration stream.

### P2 — Documentation and quality-gate drift

The README still presents Phase 4 as current and says CPU/disk are deferred, while the catalog exposes all three and API/dashboard/outbox code is present. Phase specifications 4–10 have unchecked acceptance criteria, which is correct, but feature-named commits can create a misleading impression of completion. Ruff formatting also fails on 12 files.

## Recommended next steps

Complete the repository-only work in this order, keeping each step independently tested and committed:

1. **Repair the experiment lifecycle.** Keep `active` experiments active before expiry, handle cancellation separately, add deterministic active/expiry/restart tests, and make reconciliation cleanup-first only for genuinely uncertain states.
2. **Restore schema and ownership guarantees.** Require an exact Alembic revision at runtime, implement lease renewal/fencing, and add bounded graceful-shutdown cleanup behavior.
3. **Redesign the scenario transport contract before enabling CPU/disk.** Use fixed, typed arguments that carry an opaque experiment identifier and bounded parameters without exposing a shell. Add response identity checks on every operation.
4. **Harden and test target helpers.** Add CPU quota/reserve enforcement under a dedicated non-root workload identity and process-group ownership. Add strict dedicated-storage marker validation, distinct-filesystem proof, non-sparse bounded allocation, partial-allocation handling, and experiment-owned cleanup.
5. **Wire observations end to end.** Persist bounded before/during/after HTTP and resource observations; ensure failures never block expiry or cleanup.
6. **Finish Phases 4–6 locally.** Add focused unit and disposable-target integration tests for Apache, CPU, and disk success, refusal, partial injection, timeout, restart, repeated cleanup, and operator-attention paths.
7. **Run Phase 7 hardening.** Fix formatting, add deterministic acceptance scripts, update README/spec evidence, run artifact/secret scans, and obtain operator-run Docker/container validation.
8. **Only after the CLI MVP is accepted, finish Phase 8.** Add complete API status/control/idempotency/authorization/security contracts over the same application services.
9. **Then finish Phase 9 and Phase 10.** Build the dashboard on the completed API, and connect a bounded retryable outbox to lifecycle events before independent remedy validation.
10. **Perform operator-controlled validation last.** Provision the isolated target, verify host identity and narrow privileges, run guarded real-target scenarios, and separately validate remedy attribution. Do not use a real target until repository stages 1–7 pass.

## Current go/no-go decision

**No-go for production, real-target chaos, API exposure, dashboard deployment, or remedy evaluation.**

The repository is suitable for continued local development. Read-only preflight components and much of the domain/persistence foundation are useful, but no disruptive scenario should be considered complete until the P0 findings are fixed and the applicable phase acceptance criteria have evidence.
