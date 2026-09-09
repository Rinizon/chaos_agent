# Phase 4 Specification: Apache Stop Scenario

## 1. Purpose

Phase 4 delivers the first production chaos scenario: a bounded experiment that stops the configured Apache service on the positively identified development web VM, observes the externally visible impact, and performs emergency cleanup that restores only the state changed by the experiment.

The scenario is intentionally narrow. It must not become a general service manager, remote shell, repair mechanism, or mechanism for changing Apache configuration. The production catalog contains only this reviewed scenario after implementation; CPU and disk-pressure scenarios remain unavailable.

## 2. Responsibility boundary

The chaos agent creates and withdraws one controlled Apache outage. A future remedy agent must discover the outage and perform its own repair or recovery action. Chaos cleanup is a safety mechanism and must not be reported as remedy success.

The scenario may:

- verify the configured target identity and Apache baseline;
- stop the exact configured Apache service through a fixed target helper operation;
- verify that the service is inactive and the site exhibits the expected outage;
- record bounded HTTP observations; and
- start the same service during emergency cleanup only when this experiment was proven to have stopped it.

The scenario may not:

- accept a caller-supplied service name, command, path, or shell fragment;
- stop, start, restart, reload, enable, disable, or modify any other service;
- edit Apache configuration, web content, firewall rules, packages, or system files;
- repair unrelated pre-existing Apache or website failures; or
- infer target identity from host reachability or website availability alone.

## 3. Safety invariants

Every Apache-stop experiment must satisfy all of these requirements:

- The target is the configured development VM, with the expected UUID, role, environment, and Apache service marker.
- The configured site is healthy before injection, including expected HTTP status and optional content marker.
- Apache is installed and active before injection. If it is already inactive, the experiment is refused and no service action occurs.
- The requested duration is mandatory, defaults to five minutes, and is bounded by the Phase 3 hard maximum and a scenario-specific maximum.
- Only one experiment may be active for the target.
- The injection operation is a fixed helper protocol action for the configured Apache service; no arbitrary remote command is exposed.
- The experiment records ownership evidence before entering `active`. Cleanup must be safe to retry using only persisted, validated context.
- If injection or verification is uncertain, the engine enters cleanup immediately and never injects again during reconciliation.
- Cleanup may start Apache only when persisted evidence proves this experiment stopped it. It must not start Apache after a baseline refusal or an unproven partial operation.
- Cleanup failure or post-cleanup verification uncertainty produces `operator_attention`, never false success.
- No real-target test runs by default. Real-target tests require explicit opt-in, positive environment checks, and an independently verified target configuration.

## 4. Scenario contract

### 4.1 Stable identity

- Name: `apache-stop`
- Initial version: `1.0.0`
- Description: `Stop the configured Apache service for a bounded interval and verify recovery after cleanup.`
- Required capabilities: target identity, Apache service control, Apache status verification, and external website observation.

The scenario registry must register exactly this implementation and version after Phase 4 is accepted. Database records must match both name and supported version; database values must never dynamically import code or select a fallback scenario.

### 4.2 Parameters

The initial parameter model is deliberately small:

| Parameter | Type | Default/range | Meaning |
| --- | --- | --- | --- |
| `duration_seconds` | strict integer | 300; 1 through 3600 | Maximum outage duration before expiry cleanup |

The CLI may expose duration through the existing experiment request path, but the scenario model must validate it independently and enforce the lower of the global and scenario maximums. Unknown parameters are rejected. The service name, target host, SSH options, cleanup token, and remote command are not scenario parameters.

### 4.3 Cleanup context

Persist only bounded, sanitized ownership facts, for example:

- scenario version;
- experiment ID;
- validated Apache service name;
- baseline active state;
- injection result category; and
- whether this experiment confirmed the stop operation.

Do not persist raw SSH output, complete process arguments, secrets, or unbounded diagnostics. Cleanup context must be versioned and rejected if malformed or inconsistent with the selected scenario.

## 5. Target helper and privilege contract

Extend the target helper and forced dispatcher with closed, exact operations reviewed for this scenario. The preferred protocol is:

- `apache-stop-preflight`: verify the marker-selected service is installed and active, without changing state;
- `apache-stop`: stop only the marker-selected service and return bounded JSON evidence; and
- `apache-start`: start only the marker-selected service for cleanup, returning bounded JSON evidence.

The helper must obtain the service name from the root-owned target marker or a fixed validated configuration, never from an SSH argument. It must reject extra arguments, unknown operations, malformed environment, and service-name mismatches. The dispatcher must accept only the exact operation strings and invoke a fixed argument vector.

The sudoers change must grant only these exact helper operations through the root-owned helper path. It must not grant direct `systemctl` access, a wildcard argument, a shell, or a generic service-management command. The target operations guide and isolated helper contract tests must be updated before any real-target test is considered.

## 6. Lifecycle behavior

The scenario uses the Phase 3 coordinator and supervisor without a parallel execution path:

1. Schedule a validated `apache-stop` request.
2. Persist `planned` state and the mandatory expiry.
3. Run global target preflight and scenario-specific Apache preflight.
4. Persist a healthy `before` website observation.
5. Transition to `injecting`.
6. Execute the fixed stop operation and verify Apache is inactive.
7. Persist cleanup context atomically before transitioning to `active`.
8. Record bounded `during` observations while the experiment is active.
9. On expiry, abort, cancellation, shutdown, or uncertainty, transition to cleanup.
10. Start Apache only when experiment ownership of the stop is proven.
11. Verify Apache is active, run the `after` website observation, and persist the final outcome.

Normal expiry with successful cleanup and recovery may end as `passed`. Operator cancellation with successful cleanup and recovery ends as `cancelled`. Injection refusal or a verified failure after safe cleanup ends as `failed`. Cleanup or recovery uncertainty ends as `operator_attention`.

The CLI must only schedule and request control. It must not perform stop, start, polling, cleanup, or reconciliation work in the interactive process.

## 7. Observation policy

Use the existing observer abstraction and persist observations through the Phase 3 repository. Every observation has a bounded timeout, bounded response size, timestamp, phase, status, latency, content-marker result, and stable failure category.

- `before`: required healthy baseline before injection.
- `during`: bounded observations during the outage; failures are evidence and never disable expiry or cleanup.
- `after`: required post-cleanup observation. A status mismatch, missing content marker, timeout, or unavailable site prevents `passed` or `cancelled`.

The scenario must not treat an HTTP failure alone as proof that the target service was stopped. Service-state verification and external observation are separate evidence streams.

## 8. Failure and recovery matrix

| Condition | Required behavior |
| --- | --- |
| Apache inactive during preflight | Refuse without service action; record `failed` with refusal evidence |
| Website unhealthy before injection | Refuse without service action |
| Target identity mismatch | Stop immediately; do not invoke write-capable helper operation |
| Stop operation returns failure | Treat injection as uncertain and enter cleanup only if ownership is proven |
| Stop succeeds but active verification fails | Enter cleanup; never retry injection |
| Agent restarts in `injecting` | Cleanup-first reconciliation; never re-inject |
| Experiment expires | Cleanup is mandatory and takes priority over observation |
| Abort requested | Durable cancellation request; supervisor performs cleanup |
| Start cleanup fails | Retry within bounded policy; escalate to `operator_attention` after exhaustion |
| Apache active after cleanup but website unhealthy | `failed` or `operator_attention` according to safety certainty; never `passed` |
| Apache state cannot be verified | Do not issue an unproven cleanup action; escalate to `operator_attention` |
| Repeated cleanup | Idempotent; must not affect services not owned by this experiment |

## 9. Testing requirements

### 9.1 Unit tests

Use fake transport, observer, repository, clock, and scenario dependencies to cover:

- strict parameter validation and unknown-parameter refusal;
- baseline Apache-active and website-health requirements;
- refusal when Apache is already inactive;
- successful injection, active verification, expiry, cleanup, and recovery;
- cancellation and repeated abort requests;
- stop timeout, partial injection, and uncertain verification;
- cleanup retry, idempotency, exhausted retries, and operator attention;
- unhealthy `before`, failed `during`, and unhealthy `after` observations;
- restart reconciliation from every non-terminal state; and
- absence of arbitrary service names, commands, paths, and SSH options.

### 9.2 Helper and privilege tests

Extend the disposable target contract tests to prove:

- only exact Apache operations are accepted;
- extra arguments, reordered arguments, shell metacharacters, and unknown operations are rejected;
- the service name comes only from the trusted marker;
- the unprivileged account cannot invoke the helper directly;
- the reviewed sudoers fragment allows only the exact helper operations; and
- helper output is bounded, structured, and free of secrets or raw command details.

### 9.3 Integration tests

Exercise SQLite migrations, repository audit records, scenario catalog lookup, CLI output, state transitions, and container persistence without contacting a real target. Verify no experiment row is created for an unavailable or invalid scenario.

### 9.4 Real-target test

The real-target test is opt-in and must require all of the following:

- an explicitly enabled test flag;
- a target configuration marked as development;
- an independently verified host key and target UUID;
- a disposable or approved development target;
- a clean, healthy preflight immediately before injection; and
- operator review of the cleanup and recovery procedure.

The test must inject, observe, expire or abort, clean up, verify Apache and the website, inspect audit history, and prove repeated cleanup is safe. It must not run against a hostname supplied only by an untrusted test environment variable.

## 10. Documentation and operations

Update the README and target operations guide with:

- the installed `apache-stop` scenario and its fixed duration policy;
- the exact target helper and sudoers contract;
- preflight refusal behavior when Apache or the website is already unhealthy;
- launch, status, abort, history, and reconciliation examples;
- cleanup and operator-attention procedures;
- real-target test opt-in requirements; and
- explicit confirmation that cleanup is not remedy success.

Do not document or expose a generic remote command workaround.

## 11. Acceptance criteria

Update each item only when concrete evidence exists:

- [ ] Scenario has a stable name, version, description, typed parameters, capability requirements, and bounded maximum duration.
- [ ] Production catalog registers only the reviewed `apache-stop` implementation.
- [ ] Target helper, dispatcher, and sudoers changes accept only fixed Apache operations.
- [ ] Baseline preflight refuses inactive Apache, unhealthy website, mismatched identity, and unverifiable target state without mutation.
- [ ] Injection stops only the configured Apache service and verifies the intended effect.
- [ ] Before, during, and after observations are bounded, sanitized, and persisted.
- [ ] Expiry, cancellation, shutdown, timeout, partial injection, and restart all converge on cleanup or explicit operator attention.
- [ ] Cleanup starts Apache only when ownership of the stop is proven and is safe to retry.
- [ ] Post-cleanup Apache and website verification are mandatory for success.
- [ ] CLI, audit history, state transitions, and machine-readable output are complete and tested.
- [ ] Unit, helper, migration, integration, container, and guarded real-target tests pass without leaking secrets.
- [ ] Documentation and runbooks are complete.
- [ ] No Phase 5 or Phase 6 behavior is included.
- [ ] Working tree is clean after the Phase 4 implementation commit.

## 12. Approval to begin implementation

Creating this specification does not authorize implementation, target provisioning, new sudoers permissions, real-target access, or disruptive action. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
