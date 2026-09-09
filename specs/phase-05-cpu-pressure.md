# Phase 5 Specification: CPU Pressure Scenario

## 1. Purpose

Phase 5 adds a bounded CPU-pressure experiment to the approved chaos catalog. It launches an identifiable workload on the development target for a limited duration, creates observable CPU contention, preserves capacity for SSH and cleanup, and removes only the workload owned by the experiment.

This phase does not add memory pressure, disk pressure, network disruption, root-filesystem pressure, arbitrary process termination, or remediation behavior.

## 2. Responsibility boundary

The chaos agent creates and withdraws one controlled CPU workload. A future remedy agent must independently detect, diagnose, and respond to the resulting impact. Cleanup is emergency safety behavior and must not be reported as remedy success.

The scenario may use a fixed target helper operation to launch and terminate its own workload, verify bounded resource signals, and return sanitized evidence. It may not accept arbitrary commands, executable paths, process IDs, shell fragments, or caller-selected cgroup names.

## 3. Safety invariants

- The target must be positively identified as the configured development web VM.
- Apache and the website must be healthy before injection.
- Only one experiment may be active for the target.
- Duration, worker count, and load parameters are strict, bounded, and validated before any remote operation.
- The workload must have a stable experiment-derived identity and execute in a dedicated, non-root scope.
- The workload must leave reserved CPU capacity for SSH, observations, logging, and cleanup.
- The workload must not change scheduling policy, CPU affinity of unrelated processes, system configuration, or service state.
- Cleanup must target only the experiment-owned workload and be safe to repeat.
- If ownership cannot be proven, cleanup must not guess; the outcome is `operator_attention`.
- Expiry, cancellation, timeout, lease loss, and agent restart must converge on cleanup or explicit operator attention.
- No real-target test runs by default.

## 4. Scenario contract

### 4.1 Stable identity

- Name: `cpu-pressure`
- Initial version: `1.0.0`
- Description: `Create bounded CPU pressure while preserving management and cleanup capacity.`
- Required capabilities: target identity, CPU pressure control, CPU signal verification, and website observation.

The scenario registry must register only this reviewed implementation and version. Database records must match the registered version; database values must never dynamically import code or select a fallback action.

### 4.2 Parameters

The initial model is:

| Parameter | Type | Default/range | Meaning |
| --- | --- | --- | --- |
| `duration_seconds` | strict integer | 300; 1 through 900 | Maximum pressure duration |
| `worker_count` | strict integer | 1; 1 through 8 | Number of fixed workers |
| `target_cpu_percent` | strict integer | 50; 10 through 80 | Aggregate requested CPU ceiling |

The effective CPU ceiling must preserve a configured management reserve. The scenario must reject values that could consume all logical CPUs or violate the target’s minimum SSH/cleanup reserve. Unknown parameters and caller-supplied command details are rejected.

### 4.3 Ownership context

Persist only bounded, sanitized facts required for cleanup:

- scenario version;
- experiment ID;
- validated worker count and CPU ceiling;
- fixed workload identity or target-side scope identifier; and
- confirmed ownership status.

Never persist raw process arguments, environment variables, credentials, arbitrary PIDs without an ownership scope, or unbounded command output.

## 5. Target helper and privilege contract

Add separately reviewed fixed operations to the target helper and forced dispatcher:

- `cpu-pressure-preflight`: read-only verification of CPU count, current load, reserve policy, and workload prerequisites;
- `cpu-pressure-start`: launch the fixed workload in the experiment-owned scope using validated parameters encoded by the helper protocol; and
- `cpu-pressure-stop`: terminate only the experiment-owned scope using a validated ownership token or scope identifier.

The target helper must construct the workload command internally from fixed, root-owned components. The SSH account must not choose an executable, path, signal, PID, cgroup, or shell argument. The sudoers fragment must allow only the exact helper operations and never direct shell, `systemctl`, `kill`, `pkill`, `renice`, `taskset`, or wildcard commands.

The preferred implementation should use a dedicated, non-root workload scope with an explicit CPU quota and a stable experiment identity. If the target cannot provide positive ownership and quota verification, the scenario must be refused rather than weakening the contract.

## 6. Lifecycle behavior

Use the Phase 3 supervisor and coordinator:

1. Validate and schedule the request with a mandatory expiry.
2. Run global target preflight and CPU-specific preflight.
3. Persist a healthy `before` website observation.
4. Transition to `injecting` and start the fixed workload.
5. Verify workload ownership, CPU pressure, and reserve compliance.
6. Persist cleanup context before entering `active`.
7. Record bounded `during` CPU and HTTP observations.
8. On expiry, abort, cancellation, shutdown, timeout, lease loss, or uncertainty, stop only the owned workload.
9. Verify the workload is gone, CPU reserves have recovered, and the website meets the configured policy.
10. Persist the final outcome and audit evidence.

Normal expiry with verified cleanup and recovery may end as `passed`. Operator cancellation with verified cleanup and recovery ends as `cancelled`. A verified experiment failure after safe cleanup ends as `failed`. Uncertain ownership, cleanup, or target safety ends as `operator_attention`.

## 7. Resource and observation policy

Before injection, require:

- a positive logical CPU count;
- a configured management CPU reserve;
- normalized load below the preflight ceiling;
- no conflicting active experiment workload; and
- enough memory and disk reserve for the helper, observations, and cleanup.

During injection, sample bounded read-only CPU signals and HTTP observations. Record requested versus observed pressure, load, logical CPU count, availability, latency, and stable failure categories. Observation failure must never disable expiry or cleanup.

The scenario must not claim that an HTTP failure proves CPU saturation. Target resource evidence and external website evidence remain separate.

## 8. Failure and recovery matrix

| Condition | Required behavior |
| --- | --- |
| Baseline website or target unhealthy | Refuse without starting workload |
| CPU reserve would be violated | Refuse without mutation |
| Workload start fails | Treat as failed or uncertain according to ownership evidence; never blindly stop unrelated processes |
| Pressure verification fails | Enter cleanup; never start a second workload |
| Agent restarts during injection | Cleanup-first reconciliation; never reinject |
| Experiment expires | Cleanup takes priority over further observation |
| Abort requested | Durable request; supervisor performs owned-workload cleanup |
| Workload scope cannot be located | Escalate to `operator_attention`; do not use broad process matching |
| Stop operation fails | Retry within bounded policy, then operator attention |
| CPU remains above reserve after cleanup | `failed` or `operator_attention`; never passed |
| Website remains unhealthy after cleanup | `failed` or `operator_attention`; never passed |
| Repeated cleanup | Idempotent and limited to the experiment-owned scope |

## 9. Testing requirements

### 9.1 Unit tests

Use fakes for transport, clock, observer, persistence, and resource signals to cover:

- strict parameter bounds and unknown-parameter refusal;
- management-reserve calculations and worker limits;
- healthy baseline requirements;
- successful start, pressure verification, expiry, cleanup, and recovery;
- abort, timeout, lease loss, and restart paths;
- partial start and uncertain ownership;
- cleanup retries, repeated cleanup, and operator attention;
- failed during and after observations; and
- proof that no arbitrary command, PID, signal, path, or process matcher reaches the transport.

### 9.2 Helper and privilege tests

The disposable target contract must prove:

- only exact CPU operations are accepted;
- parameters are validated and bounded by the helper;
- the workload runs in an identifiable dedicated scope;
- stop targets only that scope;
- unrelated processes cannot be terminated;
- the unprivileged account cannot invoke the helper directly; and
- sudoers grants no wildcard or general process-control privilege.

### 9.3 Integration and container tests

Exercise migrations, scenario catalog lookup, CLI output, lifecycle audit records, bounded observations, and persistence across container recreation without contacting a real target. Container tests must verify that the control-plane container itself does not gain extra capabilities or a Docker socket.

### 9.4 Real-target test

The real-target test is opt-in and requires an approved development VM, independently verified host key and UUID, clean preflight, explicit acknowledgement, and an operator-observed cleanup procedure. It must verify measurable pressure, preserved SSH access, expiry or abort cleanup, recovery, repeated cleanup safety, and audit history. It must never target a host selected solely from an untrusted test environment variable.

## 10. Documentation requirements

Update the README and target operations guide with:

- the scenario’s parameter ceilings and management reserve policy;
- the fixed helper and sudoers contract;
- workload ownership and cleanup semantics;
- refusal and operator-attention behavior;
- launch, status, abort, history, and reconciliation examples; and
- real-target test prerequisites and rollback procedures.

Do not document a generic shell, process-kill, or privilege-broadening workaround.

## 11. Acceptance criteria

Update each item only after concrete evidence exists:

- [ ] Scenario has stable identity, typed bounded parameters, capability requirements, and a maximum duration.
- [ ] Production catalog registers only the reviewed `cpu-pressure` implementation.
- [ ] CPU reserve policy prevents loss of SSH, observation, and cleanup capacity.
- [ ] Fixed helper, dispatcher, and sudoers operations cannot accept arbitrary commands or process targets.
- [ ] Workload ownership is positively established before `active`.
- [ ] Requested pressure is observable and remains within configured ceilings.
- [ ] Before, during, and after CPU/HTTP observations are bounded, sanitized, and persisted.
- [ ] Expiry, cancellation, timeout, lease loss, partial start, and restart converge on cleanup or operator attention.
- [ ] Cleanup cannot terminate unrelated processes and is safe to retry.
- [ ] Post-cleanup CPU reserve, workload absence, Apache, and website verification are mandatory.
- [ ] CLI, audit history, lifecycle transitions, and machine-readable output are complete and tested.
- [ ] Unit, helper, migration, integration, container, and guarded real-target tests pass without leaking secrets.
- [ ] Documentation and runbooks are complete.
- [ ] No memory, disk, network, or arbitrary process-disruption behavior is included.
- [ ] Working tree is clean after the Phase 5 implementation commit.

## 12. Approval to begin implementation

Creating this specification does not authorize implementation, target provisioning, new sudoers permissions, real-target access, or disruptive action. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
