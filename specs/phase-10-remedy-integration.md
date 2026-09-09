# Phase 10 Specification: Remedy-System Integration

## 1. Purpose

Phase 10 defines an independent contract between Chaos Agent and a future remedy agent. It enables controlled evaluation of detection, diagnosis, repair, and recovery without allowing the chaos agent to disclose hidden implementation details or perform remediation on the remedy agent’s behalf.

The remedy system remains a separate responsibility. Chaos Agent creates bounded incidents and performs emergency safety cleanup only. It must not diagnose the incident, suggest the repair command, restore hidden scenario state, or declare remedy success.

## 2. Responsibility boundary

Chaos Agent owns:

- approved scenario selection and bounded injection;
- target identity and preflight safety;
- experiment expiry and emergency cleanup;
- sanitized lifecycle and external-observation evidence; and
- publication of the approved integration evidence contract.

The remedy system owns:

- incident detection and alerting;
- diagnosis and causal reasoning;
- repair or recovery action;
- its own authorization, execution, and audit trail; and
- verification that the service recovered through evidence independent of Chaos Agent’s hidden state.

Neither system may invoke arbitrary commands supplied by the other. The integration must not create a shared privileged control plane.

## 3. Integration architecture

Use a narrow, versioned event or polling contract over an authenticated boundary:

```text
Chaos Agent -> sanitized experiment/observation event -> integration boundary
Remedy Agent -> independent incident, diagnosis, action, and recovery records
```

The initial implementation may publish an append-only outbox record or expose a read-only API projection. It must not synchronously call the remedy agent during injection or cleanup, and remedy-agent unavailability must never disable experiment expiry or emergency cleanup.

The integration boundary must be asynchronous, bounded, retryable, and independently observable. Delivery failure is an integration failure, not evidence that the target is healthy or unhealthy.

## 4. Event contract

### 4.1 Envelope

Every published event uses a versioned envelope containing:

- `schema_version`;
- immutable event ID;
- event type and event version;
- experiment ID;
- scenario name and version;
- non-secret target reference;
- occurred-at timestamp;
- correlation ID;
- sanitized actor or source; and
- bounded event payload.

Event IDs and experiment IDs are opaque. Do not publish SSH hosts, fingerprints, private target paths, credentials, raw process arguments, cleanup context, hidden tokens, or arbitrary command text.

### 4.2 Allowed event types

The initial contract supports:

- `experiment.scheduled`;
- `experiment.preflight_completed`;
- `experiment.injection_verified`;
- `experiment.observation`;
- `experiment.expired`;
- `experiment.cancellation_requested`;
- `experiment.cleanup_completed`;
- `experiment.finalized`; and
- `integration.delivery_failed`.

Events must describe what Chaos Agent observed and did, not what the remedy agent should do. The contract must not include a prescribed diagnosis, repair action, expected shell command, or hidden artifact identifier.

### 4.3 Payload boundaries

Publish bounded status categories, timestamps, HTTP status/latency, availability, resource-signal summaries, and sanitized evidence messages. Redact or omit response bodies, complete URLs where sensitive, target command output, process lists, file listings, private cleanup values, tokens, and environment data.

The remedy agent must be able to evaluate impact from public evidence but must not receive information that makes the expected repair mechanically obvious beyond what an independent observer could establish.

## 5. Delivery semantics

- Use an append-only outbox or equivalent durable delivery record.
- Persist the event before acknowledging the originating lifecycle transition when the event is required for audit.
- Deliver at least once with stable event IDs and consumer deduplication.
- Bound payload size, queue depth, retry count, retry delay, and retention period.
- Preserve event ordering per experiment where practical; include sequence numbers when ordering cannot be guaranteed.
- Do not block expiry, cleanup, or shutdown indefinitely on delivery.
- Mark permanently failed delivery as operator-visible integration attention without changing the experiment’s safety outcome.
- Support replay only through an authenticated, audited operator action that cannot replay target mutations.

## 6. Independent remedy workflow

The remedy system should record its own:

1. incident creation and detection timestamp;
2. evidence used for diagnosis;
3. diagnosis and confidence;
4. authorized action request and actor;
5. action result and target-side evidence;
6. recovery observation; and
7. final remedy outcome.

Chaos Agent may publish that its emergency cleanup occurred, but it must not mark the remedy workflow repaired, diagnosed, or successful. A recovery assessment must distinguish:

- recovery caused by chaos emergency cleanup;
- recovery caused by remedy action;
- recovery caused by an operator; and
- recovery not independently established.

## 7. Correlation and timing

Use opaque experiment and event identifiers for correlation. Record UTC timestamps and bounded clock-skew assumptions. Consumers must tolerate delayed, duplicated, missing, and out-of-order events.

The integration must make these intervals measurable without implying causality from timestamps alone:

- injection to detection;
- detection to diagnosis;
- diagnosis to remedy action;
- remedy action to recovery; and
- recovery observation to final classification.

Do not publish a hidden scenario cleanup token or internal process identity solely to improve correlation.

## 8. Security and authorization

- Authenticate event publication and read access independently from target SSH authentication.
- Authorize event producers, remedy consumers, replay operators, and auditors separately.
- Use runtime-injected credentials or mTLS material; never store secrets in source, images, SQLite, events, or logs.
- Apply TLS and explicit trust configuration for remote delivery.
- Prevent consumer-controlled callbacks into target operations.
- Validate all received event envelopes and reject unknown versions or oversized payloads safely.
- Treat integration input as untrusted data; never execute fields from an event as a command, path, service name, or process selector.
- Ensure remedy-agent actions cannot use Chaos Agent credentials or its target privileges.
- Redact tokens, headers, response bodies, private target identity, and hidden cleanup information from logs and audit views.

## 9. Failure and safety matrix

| Condition | Required behavior |
| --- | --- |
| Remedy consumer unavailable | Queue bounded delivery; never delay expiry or cleanup |
| Duplicate event | Consumer deduplicates by immutable event ID |
| Out-of-order event | Consumer retains sequence metadata and does not infer missing state |
| Unknown event version | Reject safely and raise integration attention |
| Delivery retries exhausted | Preserve event and mark delivery attention; do not mutate target state |
| Malformed or oversized event | Reject, audit bounded category, and do not execute payload fields |
| Chaos cleanup occurs before remedy action | Publish cleanup distinctly; do not count it as remedy success |
| Remedy action fails | Remedy system owns failure classification; Chaos Agent does not retry it as cleanup |
| Website recovers without known action | Record recovery as independently unexplained, not remedy success |
| Integration storage unavailable | Preserve experiment safety and record local integration degradation |

## 10. Testing requirements

### 10.1 Contract tests

Cover:

- event schema versions and strict unknown-field handling;
- required identifiers, timestamps, sequence, and bounded payloads;
- redaction of secrets, target details, raw output, cleanup context, and commands;
- duplicate, delayed, missing, and out-of-order events;
- producer and consumer authentication and authorization; and
- rejection of malformed, oversized, and unknown-version events.

### 10.2 Lifecycle integration tests

Use fake delivery, persistence, observer, transport, clock, and remedy consumer adapters to prove:

- lifecycle transitions produce the documented events;
- delivery failure never disables expiry or cleanup;
- cleanup and remedy outcomes remain distinct;
- replay cannot invoke target mutation;
- agent restart resumes bounded outbox delivery without duplicate target actions; and
- retention and queue limits are enforced.

### 10.3 Independent recovery tests

Use a disposable target and independently controlled remedy test double to demonstrate:

- the remedy consumer can detect impact from public observations;
- the remedy consumer does not receive hidden cleanup context or prescribed commands;
- remedy action attribution is separate from chaos cleanup attribution;
- recovery is verified independently; and
- detection, diagnosis, action, and recovery timings are measurable.

### 10.4 Security tests

Verify that compromised or malformed integration input cannot reach SSH, sudo, scenario selection, filesystem paths, process controls, or cleanup operations. Verify that a remedy credential cannot invoke Chaos Agent target operations and that event logs contain no secrets.

## 11. Documentation requirements

Document:

- event schemas and compatibility policy;
- producer and consumer authentication and authorization;
- delivery, retry, replay, retention, and failure semantics;
- public versus hidden evidence boundaries;
- incident, diagnosis, action, and recovery ownership;
- cleanup versus remedy success classification;
- clock, ordering, and correlation assumptions; and
- operator procedures for integration attention and safe replay.

Do not document a target repair command or imply that Chaos Agent can remediate incidents.

## 12. Acceptance criteria

Update each item only after concrete evidence exists:

- [ ] A versioned, authenticated, bounded event or read-only projection contract is implemented.
- [ ] Events contain sufficient public evidence for independent detection without hidden cleanup or repair information.
- [ ] No integration field can supply an arbitrary command, target, service, process, path, or cleanup action.
- [ ] Durable delivery, at-least-once deduplication, ordering metadata, retry bounds, and retention are implemented.
- [ ] Delivery failure never disables experiment expiry, emergency cleanup, or local safety state.
- [ ] Chaos cleanup, remedy action, operator intervention, and independent recovery are separately attributed.
- [ ] Remedy diagnosis and action remain outside Chaos Agent and use independent authorization.
- [ ] Authentication, authorization, TLS, replay, redaction, and malformed-input protections are tested.
- [ ] Restart, duplicate, delayed, missing, out-of-order, oversized, and unknown-version events are handled safely.
- [ ] Independent recovery validation measures detection, diagnosis, action, and recovery intervals.
- [ ] Contract, lifecycle, security, integration, and disposable-target tests pass.
- [ ] Documentation and operator runbooks are complete.
- [ ] No new chaos type, arbitrary remote execution, dashboard privilege, or hidden remediation behavior is included.
- [ ] Working tree is clean after the Phase 10 implementation commit.

## 13. Approval to begin implementation

Creating this specification does not authorize integration implementation, event publication, remedy-agent access, target access, disruptive experiments, or release changes. Implementation may begin only after this specification is reviewed and the user explicitly directs the next step.
