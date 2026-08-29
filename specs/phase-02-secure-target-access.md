# Phase 2 Specification: Secure Target Access

## Status

Complete

## Implementation history

### 2026-08-28: Step 1 completed

Delivered typed target, SSH, resource-reserve, and website settings; local SSH-material safety validation; strict versioned target-marker, helper-response, identity, resource, and preflight contracts; a closed remote-operation set; and exact target-identity refusal policy. The existing passive runtime remains valid without target configuration, and this step introduces no SSH, HTTP, subprocess, or real-target access.

Evidence:

- Pytest passed 113 tests with 93% branch-aware coverage.
- Tests cover incomplete groups, hostile hosts, root SSH use, unsafe URLs and paths, file type and mode failures, strict schema behavior, unsupported protocol versions, and every target-identity mismatch.
- Ruff formatting and lint checks passed.
- Strict mypy checks passed for `src/chaos_agent`.
- Locked dependency synchronization and source/wheel builds completed successfully.
- The Phase 1 restricted-container smoke regression passed with the passive runtime healthy.
- `git diff --check` passed.

### 2026-08-28: Step 2 completed

Delivered an application-facing remote transport boundary and a system OpenSSH adapter with a fixed closed-operation invocation, strict host-key and authentication settings, separate connect and hard process deadlines, isolated process-group termination, per-stream read limits, secret-safe error categories, and strict JSON protocol decoding into operation-specific models. Tests use local fake executables only and never open an SSH connection.

Evidence:

- Pytest passed 131 tests with 93% branch-aware coverage and warnings treated as errors.
- Fake-executable tests captured the exact argument boundary and exercised successful decoding, non-zero exits, host-key and authentication failures, scoped-privilege refusal, missing helper and executable failures, malformed and trailing JSON, schema mismatch, stdout and stderr overflow, deadline expiry, and cancellation.
- Timeout and overflow tests verified the isolated process no longer existed after termination and reaping.
- Ruff formatting and lint checks passed.
- Strict mypy checks passed for `src/chaos_agent`.
- Source distribution and wheel builds completed successfully.
- Compose validation, smoke-script syntax validation, and the full restricted-container lifecycle smoke test passed.
- `git diff --check` passed.

### 2026-08-28: Step 3 completed

Delivered a dependency-free, root-only target helper with exact `version`, `identity`, and read-only `preflight` operations; strict root-owned marker validation; bounded JSON output; fixed Apache and resource readers; an exact-match forced SSH dispatcher with a minimal replacement environment; narrow sudoers and authorized-key templates; a fictional marker; ownership/mode automation; manual provisioning, fingerprint-verification, self-test, and rollback guidance; and a disposable Linux contract-test image. No artifact installs itself or was applied to a VM.

Evidence:

- Pytest passed 164 tests with 93% branch-aware control-plane coverage and warnings treated as errors.
- Unit tests cover strict marker fields, production and wrong-role refusal, symlink and mode rejection, bounded marker input, fixed Apache commands, fixed root and `/proc` resource reads, exact dispatcher operations, empty/extended/reordered/injection-shaped command refusal, and non-root helper refusal.
- Shell syntax checks and dependency-free Python compilation passed for target artifacts.
- The disposable Linux test image passed `visudo -cf`, ownership and mode validation, all three helper operations, direct non-root refusal, the real dispatcher-to-`sudo -n` path, and extra/injection argument refusal.
- The helper test image uses only a fictional marker and fixed fake `systemctl`; it does not contact or provision a VM.
- Ruff formatting and lint checks, strict mypy, Compose validation, and the restricted control-container lifecycle smoke test passed.
- `git diff --check` passed.

### 2026-08-28: Step 4 completed

Delivered HTTPX behind an application observation interface and an ordered preflight application service that validates the local client and SSH files, negotiates the helper protocol, verifies target identity twice, confirms scoped root helper execution, evaluates Apache and resource reserves, and checks the external website only after every target prerequisite passes. Website requests reject redirects, inherit no proxy or credential environment, enforce per-I/O and total deadlines, cap decoded response bytes, and retain no response body. Reports and the stable completion log contain only sanitized outcomes and identifiers.

Evidence:

- Pytest passed 193 tests with 93% branch-aware coverage and warnings treated as errors.
- Observer tests cover status and content evidence, absence of authorization and cookie headers, redirect refusal, decoded-body limits, per-I/O failures, total request deadline, and secret-free errors.
- Application tests cover exact check order, identity and repeated-identity refusal, transport errors, scoped-sudo refusal, unsafe local files, unsupported helper versions, Apache state, root-space and memory reserves, normalized load, website failures, dependency skips, and secret-free reports and structured logs.
- No test contacts a real SSH target or website; SSH and HTTP behavior use local fakes and in-process transports.
- Locked dependency synchronization, source distribution, and wheel builds completed successfully.
- Ruff formatting and lint checks, strict mypy, Compose validation, and the restricted container lifecycle smoke test passed.
- `git diff --check` passed.

### 2026-08-28: Step 5 completed

Delivered the `chaos preflight` Typer adapter with stable human and versioned JSON output and exit codes; outbound OpenSSH client installation in the hardened image; a target-specific Compose overlay with required non-operational identity inputs and individual read-only SSH mounts; expanded image, passive-start, and preflight refusal smoke checks; guarded optional real-target validation; and complete operator documentation for configuration, provisioning, fingerprint verification, refusal handling, key rotation, rollback, and health boundaries. Phase 2 remains read-only and injects no chaos.

Evidence:

- Pytest passed 202 tests with 93% branch-aware coverage and warnings treated as errors.
- CLI tests prove unconfigured refusal occurs before application execution and validate pass, safety-refusal, local-configuration, transport, and internal-error exit behavior without exposing secrets.
- Base and target-overlay Compose configurations validated; the overlay requires an explicit UUID, host, and site URL and disables automatic creation of missing bind-file sources.
- The production image contains an OpenSSH client and no SSH daemon, root SSH directory, host keys, populated global `known_hosts`, target artifacts, credentials, or repository test content.
- The unconfigured image starts the passive agent successfully; an explicit unconfigured preflight exits `2` before target access while local container health remains independent.
- The disposable Linux target-contract image passed its helper, ownership, `visudo`, dispatcher, and scoped-sudo checks.
- The guarded real-target script refuses execution without an explicit acknowledgement, complete target identity configuration, and both reviewed SSH files. It was not run against a target.
- Locked dependency synchronization, source distribution, wheel build, Ruff, strict mypy, Compose, production-container, and target-contract gates passed.
- Repository scans found no operational target UUID, host fingerprint, SSH credential, database, or runtime state.
- `git diff --check` passed, and the completion commit leaves the working tree clean.

## 1. Purpose and measurable outcome

Phase 2 gives the chaos agent a safe, read-only path to exactly one configured development web VM. It establishes strict SSH host verification, positive application-level target identity, a fixed remote-helper protocol, a narrow non-interactive `sudo` contract, and a preflight command that refuses unhealthy or mismatched targets.

The measurable outcome is a `chaos preflight` workflow that:

- validates all target, SSH, resource-reserve, and website settings;
- verifies local SSH material without exposing it;
- connects using a dedicated unprivileged account and strict host-key checking;
- calls only fixed, allowlisted remote helper operations;
- positively identifies the expected development VM through a root-owned marker;
- verifies the helper and scoped `sudo` path;
- confirms Apache baseline state and minimum host resource reserves;
- confirms the configured website is healthy from the control VM;
- returns a clear human-readable or JSON pass/refusal result; and
- makes no change to the target VM during preflight.

Phase 2 does not inject chaos. It is complete only when an unknown, production-marked, mismatched, unhealthy, or unverifiable target is refused safely.

## 2. Scope

### 2.1 In scope

- Typed target, SSH, helper-protocol, resource-reserve, and site-health configuration.
- A transport interface independent of OpenSSH process details.
- A system OpenSSH adapter using argument arrays and no local shell.
- Strict SSH host-key verification against a dedicated `known_hosts` file.
- A dedicated, unprivileged remote account that cannot log in with a password.
- A small root-owned target helper with fixed read-only Phase 2 operations.
- A root-owned application identity marker on the development VM.
- Exact expected target-ID, environment, role, helper-version, and protocol verification.
- A documented, narrowly scoped `sudoers` policy for the target helper.
- Read-only remote facts for Apache identity/state, root free space, available memory, CPU count, and one-minute load.
- External website preflight using HTTPX with bounded timeouts.
- Application-layer preflight orchestration and stable check results.
- `chaos preflight` human and JSON output.
- OpenSSH client installation in the container without weakening Phase 1 restrictions.
- Unit, integration, container, and explicitly opted-in real-target validation boundaries.
- Operator documentation for key provisioning, host fingerprint verification, helper installation, target identity, and refusal handling.

### 2.2 Out of scope

- Any Apache stop, restart, reload, or configuration change.
- CPU, memory, disk, process, firewall, routing, DNS, or network fault injection.
- Generic remote shell or arbitrary subprocess commands.
- Uploading files during normal agent operation.
- Automatically generating, distributing, rotating, or deleting SSH credentials.
- Automatically installing the helper or changing `sudoers` on a VM.
- Experiment persistence, lifecycle, expiry, cleanup, or reconciliation.
- Continuous website observation or incident evidence timelines.
- Automatic remediation.
- API or dashboard work.
- Supporting production targets.

Provisioning artifacts may be created in the repository, but applying them to a VM is a separate operator action and requires explicit authorization.

## 3. Decisions fixed by this specification

### 3.1 SSH implementation

Use the system OpenSSH client through a typed adapter. Do not use Paramiko, AsyncSSH, shell scripts, or a generic subprocess service for remote access in Phase 2.

Reasons:

- OpenSSH provides mature host-key and key-file behavior.
- It avoids adding a second SSH and cryptography implementation to the Python runtime.
- Its exact process invocation can be inspected and tested.
- The final container can add only the distribution's `openssh-client` package without adding a daemon.

The application must invoke OpenSSH with an argument list and `shell=False`. Do not interpolate values into a local shell command.

### 3.2 Remote account

Use a dedicated account named `chaos-agent` by default.

- The account is unprivileged.
- Root SSH login is not used.
- Password and keyboard-interactive authentication are disabled.
- The account uses one dedicated Ed25519 public key.
- The account uses a root-owned standard login shell only because OpenSSH runs the forced command through that shell; interactive access remains impossible through the forced-key policy.
- The account's home, `.ssh` directory, and `authorized_keys` file are root-owned and not writable by the account.
- The account has no unrestricted `sudo` rule.
- The account cannot modify the helper, identity marker, `sudoers` policy, Apache configuration, or system binaries.
- The account's authorized key forces a root-owned dispatcher and disables agent forwarding, port forwarding, PTY allocation, and user-selected commands.

The exact authorized-key restrictions must be documented and validated against the target OpenSSH version. Do not assume an unsupported restriction works silently.

### 3.3 Two independent target-identity checks

Both of these checks are mandatory:

1. OpenSSH verifies the server host key against the dedicated, read-only `known_hosts` file.
2. The root-owned target helper returns a marker containing the configured target UUID, `development` environment, and `web` role.

A hostname, IP address, cloud instance name, SSH username, Apache banner, or website response is not sufficient target identity by itself.

### 3.4 Target marker

The target VM contains:

`/etc/chaos-agent/target.json`

Minimum schema:

```json
{
  "schema_version": 1,
  "target_id": "8d047f58-0dc7-4d61-a165-82b02edbc2c8",
  "environment": "development",
  "role": "web",
  "apache_service": "apache2.service"
}
```

Requirements:

- `target_id` is a randomly generated UUID assigned during operator provisioning.
- `environment` must equal `development` exactly.
- `role` must equal `web` exactly.
- `apache_service` must be either `apache2.service` or `httpd.service` in Phase 2.
- The directory and marker are owned by root and are not writable by the SSH account.
- The helper validates the marker strictly and refuses unknown fields or schema versions.
- Documentation examples use an unmistakably fictional UUID and must not be deployed unchanged.

### 3.5 Target helper

Install a dependency-light Python 3 helper at:

`/usr/local/libexec/chaos-agent/target-helper`

The helper is root-owned, not writable by the SSH account, and has no third-party Python dependencies. Phase 2 permits exactly these operations:

- `version`: return helper and protocol versions;
- `identity`: return the validated target marker; and
- `preflight`: return validated identity plus read-only Apache and resource facts.

The helper:

- accepts no free-form command or path;
- rejects unknown operations and extra arguments;
- emits one bounded JSON document to standard output;
- emits no secret material;
- uses stable exit codes;
- performs no file creation, deletion, service action, package action, or configuration change; and
- uses fixed local paths and system interfaces.

Later scenario phases may extend the helper through separately reviewed fixed operations. They must not add a generic command escape hatch.

### 3.6 Forced SSH dispatcher

Install a second dependency-light, root-owned program at:

`/usr/local/libexec/chaos-agent/ssh-dispatcher`

The dedicated authorized-key entry forces this dispatcher. The dispatcher reads `SSH_ORIGINAL_COMMAND`, accepts only the exact Phase 2 helper command strings, and executes a fixed argument array without `eval`, interpolation, or a child shell. Empty, unknown, repeated, reordered, or extended command strings are rejected.

The dispatcher:

- runs as the unprivileged SSH account;
- is not writable by that account;
- invokes only `sudo -n` plus the fixed helper path and one closed operation;
- clears or replaces its environment with a minimal fixed environment;
- uses no caller-supplied path or option;
- emits no diagnostic environment or command content; and
- prevents a stolen key from becoming a general unprivileged shell.

Use an authorized-key restriction equivalent to `restrict,command="/usr/local/libexec/chaos-agent/ssh-dispatcher"` only after verifying that the target OpenSSH version supports `restrict`. Documentation must also provide the explicit legacy restrictions (`no-agent-forwarding`, `no-port-forwarding`, `no-pty`, `no-user-rc`, and `no-X11-forwarding`) for reviewed environments where needed.

### 3.7 `sudo` contract

The SSH account invokes the helper only through non-interactive `sudo -n` using the exact root-owned path.

The target policy grants passwordless execution only for the approved helper path and exact Phase 2 operation arguments. It must not grant:

- `(ALL) ALL`;
- a shell, interpreter, editor, package manager, service manager, file-copy tool, or wildcard command;
- execution of a user-writable path;
- arbitrary environment preservation; or
- arbitrary helper arguments.

The repository will provide a `sudoers` fragment template and a validation command using `visudo -cf`. Provisioning documentation must require checking file ownership and mode before use.

Successful `sudo -n ... target-helper preflight` proves that the required scoped path works. The agent must not claim it has proven the absence of every other privilege; that remains a provisioning and audit responsibility.

### 3.8 Website preflight

Use HTTPX behind an observation interface. Phase 2 performs a single bounded baseline check; Phase 3 will extend the interface for experiment timelines.

- Permit `http` and `https` URLs only.
- Reject URL user information and fragments.
- Require TLS verification for HTTPS.
- Do not add a disable-verification option.
- Do not follow redirects by default.
- Bound connect, read, write, pool, and overall behavior.
- Validate the expected status and optional short content marker.
- Limit downloaded response bytes; do not buffer an unlimited body.
- Do not send credentials, cookies, or authorization headers in Phase 2.

## 4. Architecture and dependency boundaries

Use these logical boundaries:

```text
Typer CLI
   -> Preflight application service
      -> Target policy and result models
      -> Remote transport interface
         -> OpenSSH process adapter
      -> Site observer interface
         -> HTTPX adapter
      -> Clock
```

The target helper is a separately deployed target-side component, not a Python import or control-plane adapter.

Rules:

- Domain models do not import Typer, subprocess, HTTPX, or container details.
- The application service consumes typed interfaces and produces a stable `PreflightReport`.
- Only the OpenSSH adapter knows process flags and output-capture mechanics.
- Only the HTTPX adapter knows client behavior.
- The CLI renders reports and maps outcomes to exit codes; it does not decide safety policy.
- No adapter returns raw exceptions, full environments, or unbounded output to the application layer.

Suggested additions:

```text
src/chaos_agent/
├── domain/
│   ├── preflight.py
│   └── target.py
├── application/
│   └── preflight.py
└── adapters/
    ├── openssh.py
    └── http_observer.py

ops/target/
├── target-helper
├── ssh-dispatcher
├── target.json.example
├── chaos-agent.sudoers.example
└── README.md
```

Exact module names may change if the same dependency direction and responsibility boundaries are preserved.

## 5. Configuration contract

### 5.1 Target and SSH settings

Add these environment variables:

| Variable | Type/default | Validation |
| --- | --- | --- |
| `CHAOS_TARGET_ID` | required UUID | Exact expected application-level identity |
| `CHAOS_TARGET_HOST` | required string | DNS name or IP; no whitespace, URI syntax, user, or port |
| `CHAOS_TARGET_PORT` | integer, default `22` | 1–65535 |
| `CHAOS_TARGET_USER` | string, default `chaos-agent` | Conservative Linux username; `root` forbidden |
| `CHAOS_SSH_PRIVATE_KEY_PATH` | absolute path | Required regular file at runtime; no home or repository fallback |
| `CHAOS_SSH_KNOWN_HOSTS_PATH` | absolute path | Required regular file at runtime; no home or global fallback |
| `CHAOS_SSH_CONNECT_TIMEOUT_SECONDS` | integer, default `5` | 1–30 |
| `CHAOS_SSH_COMMAND_TIMEOUT_SECONDS` | integer, default `15` | 2–60 and greater than connect timeout |

Container defaults for SSH files:

- `/run/secrets/chaos-agent/ssh/id_ed25519`
- `/run/secrets/chaos-agent/ssh/known_hosts`

There are no defaults for target ID or host. The agent must remain unable to contact a target until they are set deliberately.

### 5.2 Target baseline settings

| Variable | Type/default | Validation |
| --- | --- | --- |
| `CHAOS_TARGET_APACHE_SERVICE` | default `apache2.service` | `apache2.service` or `httpd.service` only |
| `CHAOS_PREFLIGHT_MIN_ROOT_FREE_MIB` | integer, default `1024` | Conservative bounded range |
| `CHAOS_PREFLIGHT_MIN_MEMORY_AVAILABLE_MIB` | integer, default `256` | Conservative bounded range |
| `CHAOS_PREFLIGHT_MAX_LOAD_PER_CPU` | decimal, default `1.50` | Positive bounded decimal |

The configured Apache service must match the root-owned target marker and helper report exactly.

### 5.3 Website settings

| Variable | Type/default | Validation |
| --- | --- | --- |
| `CHAOS_SITE_HEALTH_URL` | required HTTP(S) URL | No user information or fragment |
| `CHAOS_SITE_EXPECTED_STATUS` | integer, default `200` | 100–599 |
| `CHAOS_SITE_EXPECTED_CONTENT` | optional string | 1–128 printable characters |
| `CHAOS_SITE_TIMEOUT_SECONDS` | decimal, default `5` | Positive and bounded |
| `CHAOS_SITE_MAX_RESPONSE_BYTES` | integer, default `65536` | Bounded to a conservative range |
| `CHAOS_SITE_CA_BUNDLE_PATH` | optional absolute path | Read-only regular file; no disable-TLS alternative |

### 5.4 Cross-field rules

- Target settings are an all-or-nothing group.
- Target environment is fixed to development and is not user-configurable.
- Target user cannot be `root`.
- SSH key and `known_hosts` paths must be different files.
- SSH command timeout must exceed connect timeout.
- SSH material paths cannot point into the application data directory.
- CA bundle path cannot point into the application data directory.
- Website URL credentials are forbidden.
- Configuration output may show target ID, host, port, user, service name, and health URL, but never file contents or secret-derived fingerprints.

### 5.5 Local SSH-file checks

Before invoking OpenSSH, verify:

- both required paths are absolute regular files and not symlinks;
- the private key is readable by the agent and has no group or other permission bits;
- `known_hosts` is readable and not writable by group or other;
- neither file is empty;
- neither path is under the repository source tree in container deployment; and
- errors identify the setting, not file contents.

Do not attempt to fix permissions automatically.

## 6. OpenSSH invocation contract

Every invocation starts from a fixed base argument list equivalent to:

```text
ssh
-F /dev/null
-o BatchMode=yes
-o IdentitiesOnly=yes
-o StrictHostKeyChecking=yes
-o UserKnownHostsFile=<validated path>
-o GlobalKnownHostsFile=/dev/null
-o PasswordAuthentication=no
-o KbdInteractiveAuthentication=no
-o ForwardAgent=no
-o ClearAllForwardings=yes
-o RequestTTY=no
-o ConnectionAttempts=1
-o ConnectTimeout=<validated seconds>
-o LogLevel=ERROR
-p <validated port>
-i <validated private key>
--
<validated user>@<validated host>
sudo -n /usr/local/libexec/chaos-agent/target-helper <fixed operation>
```

Requirements:

- Do not read user or system SSH configuration beyond the supplied options.
- Do not fall back to SSH agents, default keys, global host files, passwords, keyboard interaction, or prompts.
- Do not weaken host-key algorithms or cryptographic policy.
- Do not enable forwarding or allocate a terminal.
- Do not support proxy commands, jump hosts, local commands, environment passing, or caller-supplied OpenSSH options in Phase 2.
- The helper path and operation token are constants selected from a closed enum.
- No public method accepts an arbitrary remote command string.
- No target-derived value is reused as a command or option.

OpenSSH ultimately sends a remote command string to the server. Safety therefore depends on the command being assembled exclusively from fixed helper path and closed operation constants. Host, user, paths, port, and timeouts remain separate local OpenSSH arguments and are strictly validated.

## 7. Process execution and output safety

### 7.1 Time and process bounds

- Apply the OpenSSH connect timeout.
- Apply a separate hard process deadline around the complete invocation.
- On deadline, terminate OpenSSH, wait briefly, then kill it if necessary.
- Reap the process in every path.
- Do not leave an SSH process running after CLI cancellation.
- Map `SIGINT` to clean local cancellation without changing the target.

### 7.2 Output bounds

- Capture standard output and error separately.
- Enforce a maximum of 64 KiB per stream while reading, not only after the process exits.
- Terminate and classify the operation as protocol failure if either limit is exceeded.
- Parse successful standard output as one JSON document.
- Reject trailing non-whitespace output, malformed JSON, unknown fields, and incompatible schemas.
- Never include raw helper output in normal CLI or logs.
- Sanitize and truncate diagnostic error text before classification.

### 7.3 Error classification

Map adapter failures into stable categories such as:

- `ssh_executable_missing`;
- `connection_timeout`;
- `host_key_verification_failed`;
- `authentication_failed`;
- `connection_failed`;
- `remote_privilege_refused`;
- `helper_not_found`;
- `helper_protocol_invalid`;
- `output_limit_exceeded`; and
- `cancelled`.

Do not expose the private-key path, key material, raw target stderr, process environment, or complete OpenSSH argument list in user output.

## 8. Target-helper protocol

### 8.1 Common response envelope

Every successful response includes:

```json
{
  "protocol_version": 1,
  "helper_version": "0.1.0",
  "operation": "identity"
}
```

The control plane uses strict Pydantic response models with unknown fields forbidden.

### 8.2 Identity response

The `identity` response adds:

- target marker schema version;
- target UUID;
- environment;
- role; and
- Apache service unit.

The agent compares every value against its expectations before accepting the target.

### 8.3 Preflight response

The `preflight` response includes the identity fields plus:

```json
{
  "effective_uid": 0,
  "apache": {
    "service": "apache2.service",
    "installed": true,
    "active": true
  },
  "resources": {
    "root_free_bytes": 5368709120,
    "memory_available_bytes": 1073741824,
    "logical_cpu_count": 2,
    "load_1m": 0.25
  }
}
```

Requirements:

- Numeric values must be finite, non-negative, and conservatively bounded.
- `logical_cpu_count` must be at least one.
- The service name must match the validated marker.
- `effective_uid` must be zero, proving the approved helper operation ran through `sudo`.
- The helper determines Apache installation and active state through fixed system interfaces.
- The helper reads root filesystem capacity without accepting a caller path.
- The helper reads available memory and load without spawning a shell pipeline.

### 8.4 Helper failure output

The helper returns stable non-zero exit codes and a short error code, not a traceback or system dump. It must not echo marker contents when marker validation fails.

## 9. Preflight application behavior

### 9.1 Ordered checks

Run checks in this order and stop before later checks when their safety prerequisites are unavailable:

1. Configuration validity.
2. Local SSH client availability and version baseline.
3. Private-key and `known_hosts` file safety.
4. Strict SSH connection and helper protocol version.
5. Positive target identity.
6. Scoped `sudo` and read-only helper preflight response.
7. Expected Apache service is installed and active.
8. Root free-space reserve.
9. Available-memory reserve.
10. One-minute load per logical CPU.
11. External website status and optional content marker.

Website health must not be checked as a substitute for target identity. Conversely, a correct target identity does not make an unhealthy site pass.

### 9.2 Result model

The application returns a typed report with:

- overall outcome: `pass`, `refused`, or `error`;
- expected target ID;
- sanitized target label;
- start and completion timestamps;
- ordered checks;
- each check's stable name, `pass`/`fail`/`skip` status, safe message, and duration; and
- one stable refusal or error category when applicable.

No result in Phase 2 is persisted to SQLite. Structured logs may record the overall outcome and safe identifiers, but must not record SSH material or raw remote output.

### 9.3 Pass and refusal rules

Preflight passes only when every required check passes.

Refuse when:

- target identity is missing, malformed, production-marked, wrong role, or mismatched;
- helper or protocol version is unsupported;
- the approved `sudo` helper operation cannot run non-interactively;
- Apache is missing, mismatched, or inactive;
- a resource reserve is below its configured threshold;
- load per CPU exceeds its threshold;
- the website status or content marker is wrong; or
- any required result cannot be positively verified.

Transport and internal adapter failures produce `error`, not `pass` or a fabricated target state.

### 9.4 No mutation guarantee

The preflight service may:

- read local configuration and SSH files;
- launch the fixed OpenSSH process;
- execute the fixed read-only helper operations; and
- make a bounded unauthenticated HTTP(S) GET request.

It may not write to the target, change a service, create a remote temp file, update `known_hosts`, accept a new host key, upload a helper, or fix a failed check.

## 10. CLI contract

Add:

```text
chaos preflight [--json]
```

Human output should lead with the outcome and list checks in execution order. JSON output has a stable versioned shape suitable for the future API.

Exit codes:

- `0`: all preflight checks passed;
- `1`: a verified safety or baseline check refused the target;
- `2`: local configuration is invalid; and
- `3`: transport, helper protocol, cancellation, or internal execution error.

The CLI must not:

- accept host, user, key path, helper operation, or OpenSSH option overrides as command-line arguments;
- provide a verbose mode that prints raw OpenSSH commands or output;
- prompt to trust a host key;
- prompt for a password or passphrase; or
- offer an option to continue after a failed identity or safety check.

`chaos health` remains local-agent health only. Do not merge target or website status into the Phase 1 container health check.

## 11. Container and deployment changes

- Install only the OpenSSH client packages required for outbound SSH.
- Do not install or run an SSH server.
- Keep UID/GID 10001, read-only root, dropped capabilities, no-new-privileges, no Docker socket, and no inbound ports.
- Mount the dedicated private key and `known_hosts` read-only under `/run/secrets/chaos-agent/ssh`.
- Do not copy SSH material during image build.
- Continue starting the passive agent by default.
- Ensure `chaos preflight` can run through `docker compose exec` without changing the long-running process.
- Extend image inspection tests to prove no SSH server process, host key, private key, or populated `known_hosts` is present in the image.
- Keep the local container health check independent from remote preflight.

Compose must refuse an operational preflight through invalid or missing configuration; it must not ship a real target host, UUID, key, or fingerprint default.

## 12. Target provisioning artifacts

Repository artifacts should include:

- the root-owned helper source;
- the root-owned forced-command dispatcher source;
- a fictional target-marker example;
- a narrow `sudoers` example;
- an authorized-key restrictions example;
- file ownership and mode requirements;
- helper self-test commands;
- `visudo -cf` validation instructions;
- OpenSSH host-fingerprint verification instructions; and
- rollback instructions for removing the Phase 2 access path.

Provisioning must be manual and reviewable in Phase 2. The chaos-agent container must not provision its own privileges.

Recommended target ownership and modes:

| Path | Owner | Mode |
| --- | --- | --- |
| `/usr/local/libexec/chaos-agent/target-helper` | `root:root` | `0755` |
| `/usr/local/libexec/chaos-agent/ssh-dispatcher` | `root:root` | `0755` |
| `/etc/chaos-agent` | `root:root` | `0755` |
| `/etc/chaos-agent/target.json` | `root:root` | `0644` |
| `/etc/sudoers.d/chaos-agent` | `root:root` | `0440` |
| dedicated account home | `root:root` | `0755` or stricter |
| dedicated account `.ssh` directory | `root:root` | `0700` |
| dedicated account `authorized_keys` | `root:root` | `0600` |
| dedicated private key on control VM | agent runtime user | `0600` |
| dedicated `known_hosts` on control VM | agent runtime user | `0644` or stricter |

The SSH account must not own or be able to modify any target-side path listed in this table.

## 13. Failure modes and required behavior

| Failure | Required behavior |
| --- | --- |
| Missing target configuration | Exit `2`; invoke no network process |
| Missing or unsafe SSH file | Exit `2`; do not fix permissions |
| SSH executable missing | Exit `3`; safe actionable message |
| Unknown host key | Exit `3`; do not add or prompt |
| Changed host key | Exit `3`; refuse target and require operator review |
| Authentication failure | Exit `3`; do not fall back or prompt |
| Connect or command timeout | Terminate and reap SSH; exit `3` |
| Excess output | Terminate SSH; classify protocol failure; expose no raw output |
| Malformed helper JSON | Exit `3`; refuse identity |
| Unsupported helper protocol | Exit `1`; require compatible provisioning |
| Target UUID mismatch | Exit `1`; do not continue to host checks |
| Production or unknown environment | Exit `1`; prominent refusal |
| Wrong target role or Apache service | Exit `1` |
| Forced dispatcher rejects command | Exit `3`; expose no original command text |
| `sudo -n` refused | Exit `1`; never prompt |
| Apache inactive | Exit `1`; do not start it |
| Low disk or memory reserve | Exit `1`; do not clean files or alter memory |
| High normalized load | Exit `1`; do not terminate processes |
| Website timeout/status/content failure | Exit `1`; do not change target |
| User cancels | Reap local processes; exit `3`; make no remote cleanup claim |

## 14. Ordered implementation steps

Each step is an independently verified Git change. Follow `AGENTS.md`: inspect repository status, test the step, commit only related files, and leave the tree clean before the next prompt.

### Step 1: Target configuration and domain contracts

Deliver:

- target, SSH, reserve, and website settings;
- cross-field and file-safety validators that can be tested without network access;
- strict target marker, helper envelope, identity, resource, and preflight models;
- preflight check and report domain models;
- closed remote-operation enum; and
- configuration and model tests, including hostile values and secret-safe failures.

Verify:

- incomplete setting groups are rejected;
- root user, unsafe files, bad URLs, invalid timing, and unsupported service names are rejected;
- production, wrong-role, mismatched-ID, unknown-field, and malformed helper responses cannot validate;
- no network process is launched by configuration tests; and
- all Phase 1 and new quality gates pass.

### Step 2: Bounded OpenSSH transport

Deliver:

- remote transport interface;
- fixed OpenSSH argument builder;
- bounded process runner with hard deadline, cancellation, stream limits, and process reaping;
- safe error classification and sanitization;
- strict JSON protocol decoding; and
- fake-executable integration tests that capture argv and simulate timeout, oversized output, malformed output, stderr secrets, signals, and exit codes.

Verify:

- `shell=False` is enforced;
- exact security flags are present;
- user SSH configuration, agents, default keys, forwarding, TTY, prompts, and host-key fallback are disabled;
- no public interface accepts a raw command or option;
- hostile configuration cannot become an option or remote command;
- timeouts and cancellation leave no process behind; and
- all gates pass.

### Step 3: Target helper and privilege contract

Deliver:

- dependency-light target helper;
- forced-command dispatcher with exact-command matching;
- target marker example and strict parser;
- `sudoers` example with exact command arguments;
- authorized-key restrictions example;
- target provisioning and rollback documentation;
- helper unit tests using fake system-data adapters where practical;
- dispatcher tests for empty, exact, unknown, extended, and injection-shaped commands;
- Linux integration tests for identity, resources, Apache state abstraction, invalid marker, unknown command, extra argument, and non-root direct invocation; and
- ownership/mode validation automation for staged artifacts.

Verify:

- helper operations are read-only and emit bounded strict JSON;
- the forced dispatcher cannot open a shell or pass arbitrary arguments;
- unknown operations and extra arguments fail;
- the helper cannot accept a path or shell fragment;
- `visudo -cf` accepts the example after documented substitution;
- the SSH user cannot modify privileged artifacts; and
- no provisioning action is applied to a real VM automatically.

### Step 4: Preflight service and site observer

Deliver:

- HTTPX dependency and bounded site-observer adapter;
- application preflight orchestration in the required order;
- target identity, helper capability, Apache, reserve, normalized-load, and website policies;
- fail/skip/error report behavior;
- structured safe logs; and
- unit tests with fake SSH, HTTP, clock, and system adapters.

Verify:

- identity failure prevents later target checks;
- website success cannot override target failure;
- resource or Apache failure is never repaired;
- HTTP redirects, excessive bodies, credentials in URLs, TLS-disable behavior, and timeouts are refused or bounded as specified;
- reports contain no raw remote output or secret material; and
- all gates pass.

### Step 5: CLI, container, documentation, and acceptance

Deliver:

- `chaos preflight` human and JSON rendering with stable exit codes;
- OpenSSH client in the digest-pinned image;
- Compose target configuration without real defaults;
- individual read-only SSH material mounts;
- expanded image and container smoke checks;
- README preflight, provisioning, fingerprint, refusal, and troubleshooting guidance;
- optional, explicitly guarded real-target read-only validation procedure; and
- completed Phase 2 acceptance evidence.

Verify:

- a clean environment passes all Python and container gates;
- the image contains an SSH client but no server, credentials, or host keys;
- local container health remains independent of preflight;
- an unconfigured container starts passively but preflight refuses before network access;
- the real-target procedure cannot accept a target based on hostname alone;
- known-good dev identity can pass and a mismatched identity is refused; and
- repository status is clean after the completion commit.

## 15. Test strategy

### 15.1 Unit tests

Cover:

- every configuration boundary and cross-field rule;
- SSH file type, ownership-relevant mode, symlink, emptiness, and overlap checks;
- marker and helper schemas with unknown fields forbidden;
- target policy for UUID, environment, role, and Apache unit;
- reserve conversions and normalized load calculations;
- preflight ordering, short-circuiting, skip behavior, and overall outcome;
- safe result serialization; and
- site status, content, response-limit, redirect, and timeout behavior.

### 15.2 OpenSSH adapter tests

Use a controlled fake `ssh` executable or injected process adapter. Assert the exact argv and environment contract without contacting a host.

Cover:

- success for each closed operation;
- executable missing;
- host-key, authentication, and connection failure classification;
- process deadline and forced kill;
- cancellation;
- stdout and stderr limits;
- malformed and trailing JSON;
- secret-bearing stderr sanitization; and
- absence of shell, default config, forwarding, prompts, and arbitrary arguments.

### 15.3 Target-helper tests

Run helper tests on Linux in a container or suitable CI environment. Replace system fact readers with test seams where necessary; do not manipulate the developer's real Apache service or root filesystem.

Validate the `sudoers` template syntactically in an isolated environment containing the expected helper path and substituted account.

### 15.4 Integration tests

Provide a local isolated SSH test target or fake transport boundary that exercises host-key pinning and account restrictions without using the development VM. Tests must not weaken host-key checking for convenience.

### 15.5 Real-target validation

Real-target validation is read-only but still opt-in. It requires:

- explicit operator invocation;
- fully provisioned key and verified `known_hosts` file;
- configured expected target UUID;
- positive root-owned marker verification; and
- a known healthy site baseline.

Do not run real-target validation in the default test suite. Do not infer authorization to provision the target, edit `sudoers`, create accounts, install keys, or repair failures.

## 16. Acceptance criteria

Update an item to `[x]` only when concrete evidence exists.

### Configuration and identity

- [x] Target and SSH settings have no operational host or identity defaults.
- [x] Target user `root`, incomplete groups, unsafe files, and invalid URLs are rejected.
- [x] Strict schemas reject unknown helper fields and unsupported versions.
- [x] Host-key verification and root-owned target UUID checks are both mandatory.
- [x] Production, unknown, wrong-role, wrong-service, and mismatched targets are refused.

### Transport safety

- [x] OpenSSH uses fixed argv, `shell=False`, `/dev/null` config, strict host keys, one identity, no prompts, no forwarding, and no TTY.
- [x] Public interfaces cannot accept arbitrary remote commands or OpenSSH options.
- [x] Connect and process deadlines, cancellation, bounded streams, and process reaping are tested.
- [x] Raw output, key paths, secrets, and full invocation arguments are absent from reports and logs.
- [x] Host-key, authentication, connection, timeout, output, and helper failures are classified safely.

### Target privilege boundary

- [x] Target helper is root-owned in deployment guidance and cannot accept arbitrary commands, arguments, or paths.
- [x] Root-owned forced dispatcher rejects every command outside the exact closed operation set.
- [x] Phase 2 helper operations are demonstrably read-only.
- [x] `sudoers` template permits only exact helper operations and passes isolated `visudo` validation.
- [x] SSH authorized-key restrictions and file modes are documented.
- [x] The agent never provisions or broadens its own privileges.

### Preflight behavior

- [x] Preflight executes checks in the specified dependency order.
- [x] Apache inactive, low reserves, high normalized load, or unhealthy site produces refusal without repair.
- [x] Identity failure prevents later target checks.
- [x] Human and JSON results are stable, sanitized, and use documented exit codes.
- [x] `chaos health` remains local-only and independent from remote preflight.

### Container, testing, and documentation

- [x] Image includes an OpenSSH client but no server, keys, credentials, or host keys.
- [x] Phase 1 container restrictions remain active.
- [x] Default Python and container tests contact no real target.
- [x] Clean-environment Python, helper, image, and container gates pass.
- [x] README and target-operations guide cover provisioning, fingerprint verification, preflight, refusal, rollback, and troubleshooting.
- [x] Repository contains no operational credentials, target UUID, fingerprint, database, or runtime data.
- [x] Working tree is clean after the Phase 2 completion commit.

## 17. Documentation requirements

Update the project README with:

- the Phase 2 architecture and identity checks;
- every new setting;
- exact SSH mount expectations;
- operator-generated key and host-fingerprint workflow;
- why `ssh-keyscan` output must be verified out of band;
- helper and `sudoers` provisioning boundaries;
- `chaos preflight` output and exit codes;
- distinction among local health, target preflight, website health, and future observer results;
- safe refusal troubleshooting; and
- explicit confirmation that Phase 2 cannot inject chaos.

The target operations guide must include:

- prerequisites and supported Linux assumptions;
- manual account, directory, marker, helper, key, and `sudoers` installation;
- ownership and mode verification;
- helper self-tests;
- `visudo` validation;
- OpenSSH host-fingerprint verification through an independent channel;
- read-only preflight validation;
- key rotation; and
- complete rollback of the Phase 2 access path.

## 18. Risks, assumptions, and deferred decisions

### Risks

- OpenSSH remote commands are presented to the forced dispatcher as `SSH_ORIGINAL_COMMAND`. The root-owned dispatcher and closed fixed operations are both mandatory to avoid a shell or injection surface.
- A correct host key does not prove application environment; a correct marker does not replace host-key verification. Both must pass.
- A compromised root account on the target can falsify marker and helper output. Phase 2 protects against configuration mistakes and unintended targets, not a root-compromised VM.
- `sudoers` command matching is sensitive to exact paths and arguments. Templates must be validated on the target distribution.
- `os.access`-style local checks can differ from actual container mount behavior. Container integration tests must exercise real files.
- Website URLs can create an SSRF-like outbound request surface if configuration authority is too broad. Only trusted operators may set deployment configuration.
- Apache service names and Linux fact interfaces differ by distribution. Phase 2 supports only the two explicit service units and documented Linux assumptions.
- Host-key rotation must be treated as an operator-reviewed identity event, never auto-accepted.

### Assumptions

- The target is an isolated Linux development VM.
- The target provides OpenSSH server, `sudo`, systemd, `/proc`, `/proc/meminfo`, `statvfs`, and Python 3.
- Apache runs as either `apache2.service` or `httpd.service`.
- The control VM can reach the target's SSH port and configured site URL.
- An operator can verify the SSH host fingerprint independently.
- The dedicated key is unencrypted for non-interactive container use and protected through file permissions and deployment access controls.
- Only trusted operators can change container configuration and mounted SSH material.

### Deferred decisions

- Experiment persistence, lifecycle, locks, expiry, and reconciliation: Phase 3.
- Continuous before/during/after HTTP evidence: Phase 3.
- Write-capable helper operations: scenario-specific Phases 4–6.
- Key-management service or hardware-backed identity: post-MVP.
- Multiple targets and target selection: post-MVP.
- Bastion or jump-host support: post-MVP.
- API authorization for preflight: Phase 8.

## 19. Approval to begin implementation

Implementation may begin after this specification is accepted and committed. Acceptance of the specification authorizes repository code and provisioning-artifact development only. It does not authorize connecting to, provisioning, changing, or testing against a real VM; installing an SSH key; editing `sudoers`; or deploying the container.
