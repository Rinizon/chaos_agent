# Phase 2 Target Access Provisioning

These artifacts establish read-only, forced-command access to one isolated Linux development VM. They do not inject chaos and they are never installed automatically. Review every command and substitute values deliberately on the target console.

## Prerequisites and trust boundary

- Linux with systemd, Python 3, OpenSSH server, and `sudo`.
- Apache uses exactly `apache2.service` or `httpd.service`.
- A dedicated `chaos-agent` account and dedicated Ed25519 key are used only for this control plane.
- An operator can verify the server host-key fingerprint through the VM console or another independent trusted channel.

The example UUID and public-key placeholder are intentionally non-operational. Generate a fresh UUID for the target and never commit a real key or fingerprint.

## Reviewed installation

On the target VM, create the account without a password and with a root-owned home. The account needs a standard shell only because OpenSSH invokes the forced dispatcher through it; the authorized key prevents an interactive shell.

Install the repository artifacts as follows:

| Source | Target | Owner | Mode |
| --- | --- | --- | --- |
| `target-helper` | `/usr/local/libexec/chaos-agent/target-helper` | `root:root` | `0755` |
| `ssh-dispatcher` | `/usr/local/libexec/chaos-agent/ssh-dispatcher` | `root:root` | `0755` |
| reviewed marker | `/etc/chaos-agent/target.json` | `root:root` | `0644` |
| reviewed sudoers fragment | `/etc/sudoers.d/chaos-agent` | `root:root` | `0440` |
| reviewed authorized key | `/home/chaos-agent/.ssh/authorized_keys` | `root:root` | `0600` |

Use `root:root` mode `0755` for `/etc/chaos-agent`, and `root:root` mode `0700` for `/home/chaos-agent/.ssh`. The SSH account must not own or be able to alter any of these paths.

Replace the marker UUID with a newly generated UUID and select the real Apache unit. Replace the public-key placeholder with the dedicated public key. Do not deploy the fictional marker unchanged.

Before installing the sudoers fragment, validate a reviewed copy in an isolated root-capable environment or on the target console:

```sh
visudo -cf ./chaos-agent.sudoers.reviewed
```

After installation, run `validate-installation` as root. It checks the expected Linux ownership and modes but does not change them.

## Authorized-key compatibility

For an OpenSSH version that supports `restrict`, use the format in `authorized_keys.example`. Confirm support from the target's installed `sshd` documentation before installation.

For a reviewed older server, replace `restrict` with all explicit restrictions below while retaining the forced command:

```text
no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding,command="/usr/local/libexec/chaos-agent/ssh-dispatcher"
```

Append the dedicated public-key type, public-key data, and a comment to that single line. Never omit the forced command or any applicable restriction.

## Local self-tests

From the target console, first confirm direct unprivileged helper execution is rejected. Then test each exact allowed operation through non-interactive sudo:

```sh
sudo -u chaos-agent /usr/local/libexec/chaos-agent/target-helper version
sudo -u chaos-agent sudo -n /usr/local/libexec/chaos-agent/target-helper version
sudo -u chaos-agent sudo -n /usr/local/libexec/chaos-agent/target-helper identity
sudo -u chaos-agent sudo -n /usr/local/libexec/chaos-agent/target-helper preflight
```

The first command must report `root_required`; the three scoped `sudo -n` commands must emit one compact JSON document. Unknown operations, additional arguments, paths, and shell fragments must fail.

After the control VM has a separately verified host key and complete target configuration, run `chaos preflight --json` from the control plane. A pass must show both the pinned SSH transport and the exact marker UUID; site availability alone is insufficient.

## Host-key verification

Obtain the target's public host-key fingerprint from its console or trusted infrastructure inventory. Compare that independently obtained fingerprint with the key intended for the control VM's dedicated `known_hosts` file. Do not trust unverified `ssh-keyscan` output: it proves reachability, not identity. Never use `StrictHostKeyChecking=accept-new` or disable verification.

## Key rotation

Generate a new dedicated key through the operator's secret-management process. Add a second fully restricted forced-command entry, mount the new private key, and verify a complete preflight. Only after that pass, remove the old authorized-key entry and old private key. Host-key changes are a separate identity event: verify a changed server fingerprint independently before replacing `known_hosts`; never accept it automatically.

## Rollback

From the target console, disable access first by removing the dedicated authorized-key entry. Then remove the exact sudoers fragment, dispatcher, helper, and marker after confirming no validation is running. Finally lock or remove the dedicated account according to local policy. Remove the control VM's private key and `known_hosts` entry separately through its secret-management process.

Rollback is an operator action. The chaos-agent container cannot install, repair, broaden, or remove its own target privileges.

## Repository validation

The isolated test image installs the artifacts into a disposable Linux filesystem, validates the sudoers syntax and file modes, exercises all three read-only helper operations, proves direct non-root use fails, exercises the exact forced-command plus real `sudo -n` path, and rejects extra and injection-shaped arguments:

```sh
docker build --file ops/target/Dockerfile.test --tag chaos-agent-target-contract:test .
docker run --rm chaos-agent-target-contract:test
```

This test uses only the fictional marker and a fake fixed-behavior `systemctl` executable inside the disposable image. It provisions no VM and opens no network connection to a target.
