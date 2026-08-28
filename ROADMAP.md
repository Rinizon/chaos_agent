# Chaos Agent Project Roadmap

## Purpose

This roadmap defines the project phases and the boundary of each phase. It is the stable index used when creating detailed phase specifications.

Create detailed specifications under `specs/` using the paths listed below. A phase specification should explain exactly what will be built, how it will be tested, and what evidence proves the phase is complete. Do not use this roadmap as a substitute for a phase specification.

## Guiding architecture

The chaos agent runs as a container on a dedicated control VM. It connects to an allowlisted development web VM through a dedicated, unprivileged SSH account with narrowly scoped `sudo` permissions.

The agent injects chaos only. Its cleanup behavior is an emergency safety mechanism. Detection and remediation remain separate concerns, and a future remedy agent must not depend on hidden information from the chaos agent.

The initial interface is a Typer CLI over reusable Python application services. Later phases may expose those same services through FastAPI and a dashboard.

## Phase summary

| Phase | Name | Outcome | Detailed specification |
| --- | --- | --- | --- |
| 1 | Project foundation | Tested Python package and container development baseline | `specs/phase-01-foundation.md` |
| 2 | Secure target access | Restricted SSH transport, target identity, and preflight checks | `specs/phase-02-secure-target-access.md` |
| 3 | Experiment engine | Persistent lifecycle, expiry, cleanup, and reconciliation | `specs/phase-03-experiment-engine.md` |
| 4 | Apache stop scenario | First safe end-to-end chaos experiment | `specs/phase-04-apache-stop.md` |
| 5 | CPU pressure scenario | Bounded and observable CPU saturation experiment | `specs/phase-05-cpu-pressure.md` |
| 6 | Disk pressure scenario | Bounded pressure on dedicated test storage | `specs/phase-06-disk-pressure.md` |
| 7 | MVP hardening | Operationally dependable CLI release | `specs/phase-07-mvp-hardening.md` |
| 8 | Service API | Authenticated API and background execution model | `specs/phase-08-service-api.md` |
| 9 | Monitoring dashboard | Browser-based launch and monitoring experience | `specs/phase-09-dashboard.md` |
| 10 | Remedy-system integration | Independent incident and recovery validation contract | `specs/phase-10-remedy-integration.md` |

Phases 1 through 7 form the initial CLI MVP. Phases 8 through 10 are later product evolution and should not complicate the MVP prematurely.

## Phase 1: Project foundation

### Goal

Establish a maintainable, typed, tested, and container-first Python project without implementing disruptive behavior.

### Scope

- Python package layout with separated domain, application, and adapter boundaries.
- Typer CLI entry point with non-disruptive informational commands.
- Pydantic configuration model and safe configuration loading.
- Structured logging with secret redaction expectations.
- Pytest, formatting, linting, and type-checking baseline.
- Production-oriented Dockerfile and local Compose configuration.
- Non-root container user, persistent data mount, read-only SSH material mounts, and agent health check.
- Initial README with development and container commands.

### Exit criteria

- The package, CLI, and container start successfully.
- Automated checks pass locally.
- No credentials are stored in the repository or container image.
- The container does not require privileged mode or a Docker socket mount.

## Phase 2: Secure target access

### Goal

Connect safely to exactly the intended development VM without exposing arbitrary remote command execution.

### Scope

- SSH transport interface and implementation with strict host-key checking.
- Dedicated SSH identity and known-hosts configuration.
- Target allowlist and positive target-identity verification.
- Connection timeouts and sanitized command results.
- Fixed remote-operation abstraction; no general-purpose shell command in public interfaces.
- Preflight checks for SSH, required helper commands, scoped `sudo`, Apache identity, resource reserves, and configured site health.
- Documentation for the target account and narrow `sudoers` contract.

### Exit criteria

- The agent accepts the configured development VM and rejects an unknown or mismatched target.
- SSH failures are bounded, recorded, and do not leak secrets.
- Tests prove that unapproved operations and unsafe arguments cannot reach the transport.
- Preflight is read-only and produces a clear pass or refusal result.

## Phase 3: Experiment engine

### Goal

Provide the reusable safety and lifecycle machinery required by every chaos scenario.

### Scope

- Explicit experiment state machine and validated transitions.
- SQLAlchemy persistence with SQLite and migrations or a documented schema-evolution strategy.
- Experiment IDs, scenario versions, initiator, timestamps, parameters, events, and sanitized evidence.
- One-active-experiment-per-target lock.
- Mandatory duration, default duration, and hard maximum duration.
- Background execution independent of an interactive terminal.
- Cancellation, automatic expiry, retry-safe cleanup, verification, and final outcomes.
- Restart reconciliation for incomplete experiments.
- CLI commands for listing scenarios, status, history, abort, and reconcile.
- HTTP observation interface and persisted before/during/after observations.

### Exit criteria

- Lifecycle behavior is tested using fake SSH, HTTP, persistence, and clock adapters.
- Restart and partial-failure tests demonstrate deterministic reconciliation.
- An expired experiment always attempts cleanup.
- Cleanup failure produces an explicit operator-attention outcome rather than a false success.

## Phase 4: Apache stop scenario

### Goal

Deliver the first complete, controlled experiment by stopping Apache on the development VM.

### Scope

- Apache scenario definition, parameter model, and capability preflight.
- Narrow remote helper and `sudo` permission for the required Apache operation.
- Injection verification that Apache and the site exhibit the expected effect.
- External HTTP observations during the experiment.
- Emergency cleanup that restores only the state changed by the experiment.
- Post-cleanup Apache and website verification.
- Complete CLI and audit-history experience.

### Exit criteria

- A controlled real-target test can inject, observe, expire or abort, clean up, and verify recovery.
- Repeated cleanup is safe.
- If Apache was already stopped, preflight refuses the experiment rather than changing the baseline.
- Automated tests cover success, refusal, timeout, partial injection, and cleanup failure.

## Phase 5: CPU pressure scenario

### Goal

Create bounded CPU pressure while preserving management and cleanup capacity.

### Scope

- Validated CPU load, worker count, and duration parameters with conservative limits.
- Identifiable remote workload owned by the experiment.
- Verification of pressure through approved read-only system signals.
- Resource reserve policy that protects SSH and cleanup access.
- Targeted, retry-safe cleanup of only the experiment workload.
- HTTP latency and availability observations correlated with the experiment timeline.

### Exit criteria

- The requested pressure is observable without exceeding configured ceilings.
- Abort, expiry, transport interruption, and agent restart all converge on safe cleanup or explicit operator attention.
- Cleanup cannot terminate unrelated processes.

## Phase 6: Disk pressure scenario

### Goal

Create bounded disk pressure exclusively on dedicated test storage.

### Scope

- Positive verification of the configured dedicated test path or filesystem.
- Refusal of root, system, web-content, log, database, and other unapproved paths.
- Validated target utilization or allocation size with a mandatory free-space reserve.
- Experiment-specific, identifiable allocation artifacts.
- Safe handling of partial allocation, full-device errors, abort, and expiry.
- Targeted cleanup and post-cleanup capacity verification.
- HTTP observations correlated with the experiment timeline.

### Exit criteria

- The scenario cannot target the root filesystem or escape the dedicated test location.
- The configured reserve remains available throughout tested normal operation.
- Cleanup removes only experiment-owned artifacts and is safe to retry.

## Phase 7: MVP hardening

### Goal

Turn the first three scenarios into an operationally dependable CLI release.

### Scope

- End-to-end test matrix across supported scenarios.
- Container restart, host restart, SSH interruption, stale lock, database recovery, and cleanup-failure exercises.
- Consistent human-readable and machine-readable CLI output.
- Audit-history review and secret-redaction verification.
- Operator runbooks for deployment, key rotation, preflight refusal, abort, reconciliation, and manual emergency handling.
- Versioning, release notes, backup expectations, and upgrade procedure.
- Documented MVP limitations and deferred risks, including memory and network chaos.

### Exit criteria

- All supported scenarios meet the definition of done in `AGENTS.md`.
- A clean VM can deploy the container using documented steps.
- An operator can identify active, completed, failed, and attention-required experiments.
- Recovery drills demonstrate that the chaos agent does not become the only path to target recovery.

## Phase 8: Service API

### Goal

Expose the proven application services through a secured API without duplicating CLI business logic.

### Scope

- FastAPI adapter over existing application services.
- Authentication, authorization, request validation, and audit attribution.
- Background job supervision and safe concurrency controls.
- Experiment launch, status, event history, abort, scenario catalog, target health, and agent health endpoints.
- Streaming or polling contract for live status.
- API versioning and OpenAPI documentation.

### Exit criteria

- CLI and API produce equivalent lifecycle behavior through the same core services.
- Unauthorized callers cannot view sensitive configuration or launch experiments.
- API process restarts do not orphan active experiments silently.

## Phase 9: Monitoring dashboard

### Goal

Provide a browser interface for monitoring the agent and site and for safely launching approved scenarios.

### Scope

- Agent, target, and website status views that clearly distinguish their health states.
- Scenario catalog and validated experiment-launch workflow.
- Prominent target identity, impact, duration, and safety-limit confirmation.
- Live experiment timeline, HTTP observations, expiry, cleanup, and final result.
- History and audit-detail views.
- Abort action with clear status feedback.
- Authentication and authorization aligned with the service API.

### Exit criteria

- The dashboard never bypasses server-side validation or safety policies.
- Operators can distinguish injection success, site impact, cleanup success, and final recovery.
- Loss of the dashboard does not stop expiry, cleanup, observation, or reconciliation.

## Phase 10: Remedy-system integration

### Goal

Validate a separately built remedy system without giving it the chaos agent's answer key.

### Scope

- Stable, minimal experiment and observation integration contract.
- Independent observer or judge for detection and recovery outcomes.
- Ordinary operational signals for the remedy system: monitoring, alerts, metrics, logs, and its authorized target access.
- Explicit separation between injected-fault metadata and information available to the remedy system.
- Timelines and pass criteria for detection, diagnosis, approved remediation, service recovery, and absence of unrelated damage.
- Emergency cleanup policy that does not falsely count as remedy success.

### Exit criteria

- The remedy system can be evaluated without direct access to hidden scenario details.
- The independent judge, not either agent, determines recovery success.
- Results distinguish chaos cleanup, remedy action, and operator intervention.

## Rules for phase specifications

Create one specification per phase using the filename listed in the phase summary. Each specification should contain:

1. Purpose and measurable outcome.
2. In-scope and out-of-scope behavior.
3. User and operator workflows.
4. Architecture and component boundaries.
5. Configuration and data-model changes.
6. Security and safety requirements.
7. Failure modes and recovery behavior.
8. Ordered implementation steps.
9. Test plan and real-target validation boundaries.
10. Acceptance criteria and completion evidence.
11. Documentation and deployment updates.
12. Risks, assumptions, and deferred decisions.

Before implementation starts, resolve any open decision that would materially change the phase architecture. During implementation, keep the phase specification current and mark acceptance criteria complete only when supporting evidence exists.

## Phase-change policy

- Complete phases in order unless the roadmap is deliberately revised.
- A later phase must not weaken an earlier safety invariant.
- Split a phase when its specification cannot be implemented and reviewed as a coherent, independently verifiable increment.
- Update this roadmap when phase boundaries or outcomes change.
- Record detailed implementation decisions in the relevant phase specification rather than expanding this roadmap indefinitely.
