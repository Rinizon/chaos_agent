"""Static safety checks for target-side provisioning artifacts."""

import os
import subprocess
from pathlib import Path

REPOSITORY = Path(__file__).parents[2]
TARGET = REPOSITORY / "ops/target"


def test_executable_artifacts_have_repository_execute_bits() -> None:
    for name in ("target-helper", "ssh-dispatcher", "validate-installation"):
        assert os.stat(TARGET / name).st_mode & 0o111 == 0o111


def test_sudoers_has_only_exact_closed_helper_operations() -> None:
    sudoers = (TARGET / "chaos-agent.sudoers.example").read_text(encoding="utf-8")

    assert "NOPASSWD: CHAOS_AGENT_PHASE2" in sudoers
    assert "target-helper version" in sudoers
    assert "target-helper identity" in sudoers
    assert "target-helper preflight" in sudoers
    assert " ALL\n" not in sudoers
    assert "*" not in sudoers


def test_authorized_key_forces_dispatcher_and_has_no_real_key() -> None:
    authorized_key = (TARGET / "authorized_keys.example").read_text(encoding="utf-8")

    assert authorized_key.startswith(
        'restrict,command="/usr/local/libexec/chaos-agent/ssh-dispatcher"'
    )
    assert "REPLACE_WITH_DEDICATED_PUBLIC_KEY" in authorized_key


def test_marker_is_fictional_and_strictly_development() -> None:
    marker = (TARGET / "target.json.example").read_text(encoding="utf-8")

    assert '"target_id": "00000000-0000-4000-8000-000000000000"' in marker
    assert '"environment": "development"' in marker


def test_real_target_validation_requires_explicit_acknowledgement() -> None:
    script = REPOSITORY / "scripts/real-target-preflight.sh"

    result = subprocess.run(
        [str(script), "--json"],
        check=False,
        capture_output=True,
        text=True,
        env={},
        timeout=5,
    )

    assert result.returncode == 2
    assert "explicit acknowledgement is required" in result.stderr


def test_target_compose_overlay_has_no_operational_identity_defaults() -> None:
    overlay = (REPOSITORY / "compose.target.yaml.example").read_text(encoding="utf-8")

    assert "CHAOS_TARGET_ID:?" in overlay
    assert "CHAOS_TARGET_HOST:?" in overlay
    assert "CHAOS_SITE_HEALTH_URL:?" in overlay
    assert "create_host_path: false" in overlay
    assert "id_ed25519" in overlay
    assert "known_hosts" in overlay
