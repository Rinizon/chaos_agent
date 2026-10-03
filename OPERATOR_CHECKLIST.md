# Operator Checklist for MVP Validation

This checklist contains work that requires your infrastructure, trust decisions, credentials, or authorization. Repository-only implementation remains tracked in `SPEC.md`.

Do not run a disruptive experiment until the relevant scenario is marked complete in `SPEC.md`, all local acceptance checks pass, and the isolated target has an independently verified recovery path.

## 1. Provide Docker validation

- [ ] Confirm Docker Desktop or Docker Engine is running and available to your account.
- [ ] Run the hardened agent container smoke test:

  ```sh
  ./scripts/container-smoke.sh
  ```

- [ ] Run the disposable target-contract image:

  ```sh
  docker build --file ops/target/Dockerfile.test --tag chaos-agent-target-contract:test .
  docker run --rm chaos-agent-target-contract:test
  ```

- [ ] Preserve the output and record the Docker/OS versions used.

These tests must pass without privileged mode, a Docker socket mount, embedded credentials, or network access to a real target.

## 2. Provision an isolated development target

- [ ] Create or designate a disposable Linux VM that cannot affect production systems.
- [ ] Confirm it uses systemd and exactly `apache2.service` or `httpd.service`.
- [ ] Ensure console or hypervisor access remains available independently of SSH and the chaos agent.
- [ ] Take a tested snapshot or establish another independently verified recovery method.
- [ ] Generate a unique target UUID and record it in your trusted inventory.
- [ ] Confirm the target has adequate CPU, memory, root-disk reserve, and separate dedicated test storage.
- [ ] Do not reuse production credentials, host keys, data, DNS names, monitoring secrets, or network access.

## 3. Review and install the restricted target access path

Follow `ops/target/README.md` from the target console.

- [ ] Create the dedicated unprivileged `chaos-agent` SSH account.
- [ ] Independently review `target-helper`, `ssh-dispatcher`, the sudoers template, and authorized-key restrictions.
- [ ] Replace the fictional marker with the verified target UUID and correct Apache service.
- [ ] Validate the sudoers file with `visudo -cf` before installation.
- [ ] Install every artifact with the documented root ownership and modes.
- [ ] Run `/usr/local/libexec/chaos-agent/validate-installation` as root.
- [ ] Confirm direct helper execution as the SSH account fails.
- [ ] Confirm only exact, reviewed `sudo -n` operations succeed.
- [ ] Confirm an interactive shell, port forwarding, agent forwarding, PTY, extra arguments, and unknown commands are refused.

Do not broaden sudo permissions to troubleshoot a failed test.

## 4. Create and protect SSH material

- [ ] Generate a dedicated Ed25519 key using your secret-management process.
- [ ] Install only the restricted public-key entry on the development target.
- [ ] Obtain the target host-key fingerprint from its console or another trusted inventory.
- [ ] Compare the fingerprint independently before writing `known_hosts`; do not trust unverified `ssh-keyscan` output.
- [ ] Store the private key at `secrets/ssh/id_ed25519` with owner-read-only permissions.
- [ ] Store the pinned host entry at `secrets/ssh/known_hosts` read-only.
- [ ] Confirm neither file is committed, copied into an image, or exposed in logs.

## 5. Prepare persistent agent state

- [ ] Create the persistent Docker volume or host storage for `/var/lib/chaos-agent`.
- [ ] Stop the agent before schema migration or restore operations.
- [ ] Apply the explicit migration to the persistent database:

  ```sh
  CHAOS_DATABASE_URL=sqlite:////absolute/path/to/chaos-agent.db uv run alembic upgrade head
  ```

- [ ] Verify `uv run alembic current` reports `0004 (head)` using the same URL.
- [ ] Establish a database-aware SQLite backup and restore procedure; never copy a live WAL database as a single file.
- [ ] Test a restore while the agent is stopped.

## 6. Configure and run read-only preflight

- [ ] Set the verified `CHAOS_TARGET_ID`, host, port, user, Apache unit, and external site-health URL.
- [ ] Set conservative resource reserves for the actual VM size.
- [ ] If HTTPS uses a private CA, mount only the reviewed CA bundle; never disable TLS verification.
- [ ] Start with read-only preflight only:

  ```sh
  CHAOS_REAL_TARGET_ACK=I_ACKNOWLEDGE_READ_ONLY_DEV_PREFLIGHT \
    ./scripts/real-target-preflight.sh --json
  ```

- [ ] Verify the result binds the pinned SSH host key, exact target UUID, development/web role, Apache baseline, resource reserves, and external website health.
- [ ] Investigate any refusal from the target console; do not weaken identity or reserve checks.

## 7. Authorize guarded scenario validation

Perform this section only after the scenario's repository criteria are complete and a separate operator has reviewed the target helper changes.

- [ ] Approve an explicit maintenance window and maximum duration.
- [ ] Ensure console access and an independent recovery operator are present.
- [ ] Test `apache-stop` first: normal expiry, abort, agent restart, and repeated cleanup.
- [ ] Verify the site impact is externally observed and Apache/site recovery is independently confirmed.
- [ ] Test `cpu-pressure` only after its non-root quota and process-ownership gates are complete.
- [ ] Test `disk-pressure` only on verified separate test storage after its real-allocation and ownership gates are complete.
- [ ] Confirm root filesystem, management access, logging, and cleanup reserves remain available.
- [ ] Preserve experiment history, transition records, observations, and sanitized logs.
- [ ] Treat any `operator_attention` result as a stop condition for further experiments.

## 8. Make the MVP release decision

- [ ] Confirm `./scripts/release-check.sh` passes from a clean checkout.
- [ ] Confirm both Docker checks pass.
- [ ] Confirm all three guarded real-target scenario matrices pass.
- [ ] Review repository, images, logs, database records, and artifacts for credentials or operational target data.
- [ ] Verify backup, restore, key rotation, abort, reconciliation, emergency, and rollback runbooks.
- [ ] Record versions, evidence, known limitations, and rollback criteria in the release record.
- [ ] Approve MVP only if Phases 1–7 meet their acceptance criteria.

API exposure, dashboard deployment, and independent remedy validation are post-MVP work and require separate authentication, TLS, network, and observer decisions.
