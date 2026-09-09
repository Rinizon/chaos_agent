# Phase 6 Specification: Disk Pressure Scenario

## 1. Purpose

Phase 6 adds a bounded disk-pressure experiment that consumes space only on explicitly approved dedicated test storage. It creates an identifiable experiment-owned allocation, records its effect, and removes only that allocation during emergency cleanup.

This phase does not permit root-filesystem pressure, memory pressure, network disruption, arbitrary file creation, web-content modification, log/database filling, or remediation behavior.

## 2. Responsibility boundary

The chaos agent creates and withdraws one controlled disk-pressure artifact. A future remedy agent must independently detect and respond to the resulting impact. Cleanup is an emergency safety mechanism and must not be reported as remedy success.

The scenario may use fixed target-helper operations to verify an approved test filesystem, allocate bounded experiment-owned storage, verify capacity effects, and remove that allocation. It may not accept arbitrary paths, filenames, shell fragments, mount operations, device paths, or caller-selected deletion targets.

## 3. Safety invariants

- The target must be positively identified as the configured development web VM.
- Apache and the website must be healthy before injection.
- Only one experiment may be active for the target.
- The target path or filesystem must be explicitly configured as dedicated test storage and positively verified before every mutating operation.
- Root, system, web-content, log, database, container, home, temporary, and unknown filesystems must be refused.
- The allocation must preserve a configured free-space reserve and must not rely on filling a filesystem until an error occurs.
- Allocation size, chunk size, duration, and cleanup attempts must be strictly bounded.
- Every artifact must have a stable experiment-derived identity and be owned by the experiment.
- Cleanup must remove only the proven experiment-owned artifact and be safe to repeat.
- If storage identity or artifact ownership cannot be proven, cleanup must not guess; the outcome is `operator_attention`.
- Expiry, cancellation, timeout, lease loss, and agent restart must converge on cleanup or explicit operator attention.
- No real-target test runs by default.

## 4. Scenario contract

### 4.1 Stable identity

- Name: `disk-pressure`
- Initial version: `1.0.0`
- Description: `Create bounded disk pressure on dedicated test storage while preserving a configured free-space reserve.`
- Required capabilities: target identity, dedicated test-storage verification, bounded allocation, capacity verification, and website observation.

The scenario registry must register only this reviewed implementation and version. Database records must match the registered version; database values must never dynamically import code or select a fallback action.

### 4.2 Parameters

The initial model is:

| Parameter | Type | Default/range | Meaning |
| --- | --- | --- | --- |
| `duration_seconds` | strict integer | 300; 1 through 900 | Maximum pressure duration |
| `allocation_mib` | strict integer | 256; 1 through 4096 | Maximum allocated test data |
| `chunk_mib` | strict integer | 16; 1 through 64 | Bounded allocation chunk size |

The scenario must reject any request whose allocation would reduce verified free space below the configured reserve. Unknown parameters and caller-supplied paths or filenames are rejected. The approved test-storage identity must come from trusted configuration and target-side verification, never from an arbitrary CLI argument.

### 4.3 Ownership context

Persist only bounded, sanitized facts required for cleanup:

- scenario version;
- experiment ID;
- verified filesystem identity;
- approved test-storage scope;
- allocation size and chunk size; and
- artifact ownership identifier.

Never persist raw command output, arbitrary paths, credentials, environment variables, unbounded file listings, or deletion instructions supplied by a caller.

## 5. Dedicated-storage contract

The target must expose a dedicated test filesystem or directory provisioned outside the application’s normal data, web, log, and system paths. The target marker or a separate root-owned test-storage marker must identify:

- canonical storage path or filesystem ID;
- expected filesystem type or mount identity;
- development-only environment;
- dedicated-test purpose; and
- minimum free-space reserve.

The helper must resolve and verify the canonical identity using fixed, read-only operations. It must refuse symlinks, path traversal, bind-mounted application paths, root filesystem identity, and paths whose ownership or permissions do not meet policy. A directory name alone is not sufficient proof of dedicated storage.

## 6. Target helper and privilege contract

Add separately reviewed fixed operations to the target helper and forced dispatcher:

- `disk-pressure-preflight`: verify dedicated-storage identity, free capacity, reserve, and allocation prerequisites without mutation;
- `disk-pressure-start`: allocate the validated bounded artifact in the verified test-storage scope; and
- `disk-pressure-stop`: remove only the artifact identified by persisted experiment ownership.

The helper must construct the artifact path internally from the verified storage scope and immutable experiment identity. The SSH account must not choose a path, filename, device, mount, deletion pattern, or shell command. The sudoers fragment must allow only the exact helper operations and must not grant direct filesystem utilities, `rm`, `dd`, mount commands, or wildcard arguments.

Allocation must use bounded writes with explicit error handling and reserve checks. It must record partial allocation safely so a failed or interrupted start converges on cleanup without scanning or deleting unrelated files.

## 7. Lifecycle behavior

Use the Phase 3 supervisor and coordinator:

1. Validate and schedule the request with a mandatory expiry.
2. Run global target preflight and dedicated-storage preflight.
3. Persist a healthy `before` website observation.
4. Transition to `injecting` and verify the storage identity again.
5. Allocate bounded pressure in chunks while preserving the reserve.
6. Verify artifact ownership, allocation size, and remaining free capacity.
7. Persist cleanup context before entering `active`.
8. Record bounded `during` capacity and HTTP observations.
9. On expiry, abort, cancellation, shutdown, timeout, lease loss, or uncertainty, remove only the owned artifact.
10. Verify artifact absence, storage reserve recovery, Apache health, and website health.
11. Persist the final outcome and audit evidence.

Normal expiry with verified cleanup and recovery may end as `passed`. Operator cancellation with verified cleanup and recovery ends as `cancelled`. A verified failure after safe cleanup ends as `failed`. Uncertain storage identity, artifact ownership, cleanup, or recovery ends as `operator_attention`.

## 8. Resource and observation policy

Before injection, require:

- a positive dedicated-storage identity;
- free capacity above reserve plus the requested allocation and safety margin;
- no conflicting active experiment artifact;
- sufficient root, memory, and database reserves for control-plane operation; and
- a healthy Apache and website baseline.

During injection, sample bounded free-space and HTTP observations. Record requested allocation, successfully allocated amount, remaining free bytes, filesystem identity category, availability, latency, and stable failure categories. Observation failure must never disable expiry or cleanup.

The scenario must not claim that an HTTP failure proves disk exhaustion. Storage capacity evidence and external website evidence remain separate.

## 9. Failure and recovery matrix

| Condition | Required behavior |
| --- | --- |
| Storage identity is missing or mismatched | Refuse without allocation |
| Path resolves to root, system, web, log, database, home, or unknown storage | Refuse without mutation |
| Reserve is insufficient | Refuse without mutation |
| Allocation fails partway | Persist partial ownership and enter cleanup |
| Agent restarts during allocation | Cleanup-first reconciliation; never allocate again |
| Experiment expires | Cleanup takes priority over further observation |
| Abort requested | Durable request; supervisor performs owned-artifact cleanup |
| Artifact ownership cannot be proven | Escalate to `operator_attention`; do not scan or delete broadly |
| Cleanup fails | Retry within bounded policy, then operator attention |
| Free-space reserve does not recover | `failed` or `operator_attention`; never passed |
| Website remains unhealthy after cleanup | `failed` or `operator_attention`; never passed |
| Repeated cleanup | Idempotent and limited to the experiment-owned artifact |

## 10. Testing requirements

### 10.1 Unit tests

Use fakes for transport, filesystem facts, observer, persistence, clock, and allocation results to cover:

- strict parameter bounds and unknown-parameter refusal;
- dedicated-storage identity checks;
- refusal of root, system, web, log, database, home, symlink, and unknown paths;
- reserve and allocation calculations;
- successful bounded allocation, expiry, cleanup, and recovery;
- partial allocation, write errors, timeout, cancellation, lease loss, and restart;
- cleanup retries, repeated cleanup, and operator attention;
- failed during and after observations; and
- proof that no arbitrary path, filename, deletion pattern, device, or shell argument reaches the transport.

### 10.2 Helper and privilege tests

The disposable target contract must prove:

- only exact disk-pressure operations are accepted;
- allocation arguments are validated and bounded by the helper;
- root and non-dedicated filesystems are refused;
- artifacts are created only within the approved test-storage scope;
- cleanup cannot remove unrelated files;
- partial allocation leaves a recoverable ownership record;
- the unprivileged account cannot invoke the helper directly; and
- sudoers grants no wildcard or general filesystem privilege.

### 10.3 Integration and container tests

Exercise migrations, catalog lookup, CLI output, lifecycle audit records, bounded capacity observations, and persistence across container recreation without contacting a real target. Verify the control-plane container cannot access the Docker socket or target storage directly.

### 10.4 Real-target test

The real-target test is opt-in and requires an approved development VM, independently verified host key and UUID, a dedicated disposable test filesystem, clean preflight, explicit acknowledgement, and an operator-observed cleanup procedure. It must verify measurable allocation, preserved free-space reserve, SSH access, expiry or abort cleanup, recovered capacity, repeated cleanup safety, and audit history. It must never target a path selected solely by an untrusted test environment variable.

## 11. Documentation requirements

Update the README and target operations guide with:

- dedicated-storage provisioning and identity requirements;
- allocation, chunk, reserve, and duration ceilings;
- the fixed helper and sudoers contract;
- artifact ownership and cleanup semantics;
- refusal and operator-attention behavior;
- launch, status, abort, history, and reconciliation examples; and
- real-target test prerequisites and rollback procedures.

Do not document generic filesystem commands, arbitrary cleanup patterns, or privilege-broadening workarounds.

## 12. Acceptance criteria

Update each item only after concrete evidence exists:

- [ ] Scenario has stable identity, typed bounded parameters, capability requirements, and a maximum duration.
- [ ] Production catalog registers only the reviewed `disk-pressure` implementation.
- [ ] Dedicated-storage identity is positively verified before every mutation.
- [ ] Root, system, web, log, database, home, symlink, and unknown storage targets are refused.
- [ ] Free-space reserve calculations prevent unsafe allocation.
- [ ] Fixed helper, dispatcher, and sudoers operations cannot accept arbitrary paths or commands.
- [ ] Allocation artifacts are experiment-owned, bounded, and recoverable after partial failure.
- [ ] Before, during, and after capacity/HTTP observations are bounded, sanitized, and persisted.
- [ ] Expiry, cancellation, timeout, lease loss, partial allocation, and restart converge on cleanup or operator attention.
- [ ] Cleanup cannot remove unrelated files and is safe to retry.
- [ ] Post-cleanup artifact absence, capacity reserve, Apache, and website verification are mandatory.
- [ ] CLI, audit history, lifecycle transitions, and machine-readable output are complete and tested.
- [ ] Unit, helper, migration, integration, container, and guarded real-target tests pass without leaking secrets.
- [ ] Documentation and runbooks are complete.
- [ ] No memory, CPU-pressure, network, root-filesystem, or arbitrary filesystem behavior is included.
- [ ] Working tree is clean after the Phase 6 implementation commit.

## 13. Approval to begin implementation

Creating this specification does not authorize implementation, target provisioning, new sudoers permissions, real-target access, or disruptive action. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
