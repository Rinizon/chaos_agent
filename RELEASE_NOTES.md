# Chaos Agent 0.1.0

## Scope

This release contains the CLI foundations, secure target preflight, durable experiment engine, and reviewed contracts for `apache-stop`, `cpu-pressure`, and `disk-pressure`.

## Release status

The scenario contracts and local validation tests are present. A production MVP release is not approved until the Phase 7 hardening gates pass, including supervised runtime wiring, container smoke validation, and guarded end-to-end lifecycle tests.

## Safety limitations

- Chaos cleanup is emergency safety behavior, not remediation.
- Real-target experiments require explicit operator approval and independently verified development-target identity.
- Memory pressure, network disruption, root-filesystem pressure, and arbitrary remote commands are not supported.
- Keep SQLite on local persistent storage and back it up with a database-aware SQLite backup operation while the agent is stopped.

## Upgrade

Stop the agent, create and verify a consistent SQLite backup, apply the explicit Alembic migration, then start the agent and check local health. Do not copy a live WAL database file or bypass schema refusal.
