"""Static safety checks for target-side provisioning artifacts."""

import os
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
