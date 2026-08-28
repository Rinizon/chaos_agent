"""Tests for the dependency-free, read-only target helper artifact."""

import json
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPOSITORY = Path(__file__).parents[2]
HELPER_PATH = REPOSITORY / "ops/target/target-helper"
MARKER = {
    "schema_version": 1,
    "target_id": "8d047f58-0dc7-4d61-a165-82b02edbc2c8",
    "environment": "development",
    "role": "web",
    "apache_service": "apache2.service",
}


@pytest.fixture(scope="module")
def helper() -> dict[str, Any]:
    return runpy.run_path(str(HELPER_PATH), run_name="target_helper_tests")


def test_marker_parser_accepts_exact_development_marker(
    helper: dict[str, Any], tmp_path: Path
) -> None:
    marker_path = tmp_path / "target.json"
    marker_path.write_text(json.dumps(MARKER), encoding="utf-8")

    assert helper["read_marker"](marker_path, enforce_ownership=False) == MARKER


@pytest.mark.parametrize(
    "change",
    [
        {"extra": "refused"},
        {"schema_version": 2},
        {"target_id": "not-a-uuid"},
        {"apache_service": "nginx.service"},
        {"environment": "production"},
        {"role": "database"},
    ],
)
def test_marker_parser_refuses_invalid_or_unsafe_identity(
    helper: dict[str, Any], tmp_path: Path, change: dict[str, object]
) -> None:
    marker_path = tmp_path / "target.json"
    marker_path.write_text(json.dumps(MARKER | change), encoding="utf-8")

    with pytest.raises(helper["HelperFailure"]):
        helper["read_marker"](marker_path, enforce_ownership=False)


def test_marker_parser_rejects_symlink(helper: dict[str, Any], tmp_path: Path) -> None:
    marker_path = tmp_path / "target.json"
    real_marker = tmp_path / "real-target.json"
    real_marker.write_text(json.dumps(MARKER), encoding="utf-8")
    marker_path.symlink_to(real_marker)

    with pytest.raises(helper["HelperFailure"]):
        helper["read_marker"](marker_path, enforce_ownership=False)


def test_marker_parser_rejects_writable_or_oversized_file(
    helper: dict[str, Any], tmp_path: Path
) -> None:
    marker_path = tmp_path / "target.json"
    marker_path.write_text(json.dumps(MARKER), encoding="utf-8")
    marker_path.chmod(0o666)
    with pytest.raises(helper["HelperFailure"]):
        helper["read_marker"](marker_path, enforce_ownership=False)

    marker_path.chmod(0o644)
    marker_path.write_text("x" * 4097, encoding="utf-8")
    with pytest.raises(helper["HelperFailure"]):
        helper["read_marker"](marker_path, enforce_ownership=False)


def test_version_does_not_read_marker(helper: dict[str, Any]) -> None:
    def forbidden_reader() -> dict[str, Any]:
        raise AssertionError("version must not read the marker")

    assert helper["build_response"]("version", marker_reader=forbidden_reader) == {
        "protocol_version": 1,
        "helper_version": "0.1.0",
        "operation": "version",
    }


def test_identity_returns_only_validated_marker_fields(helper: dict[str, Any]) -> None:
    response = helper["build_response"]("identity", marker_reader=lambda: MARKER)

    assert response["target_id"] == MARKER["target_id"]
    assert response["environment"] == "development"
    assert "resources" not in response


def test_preflight_combines_fixed_read_only_facts(helper: dict[str, Any]) -> None:
    response = helper["build_response"](
        "preflight",
        marker_reader=lambda: MARKER,
        apache_reader=lambda service: {"service": service, "installed": True, "active": True},
        resources_reader=lambda: {
            "root_free_bytes": 4096,
            "memory_available_bytes": 2048,
            "logical_cpu_count": 2,
            "load_1m": 0.25,
        },
    )

    assert response["effective_uid"] == 0
    assert response["apache"] == {
        "service": "apache2.service",
        "installed": True,
        "active": True,
    }
    assert response["resources"]["logical_cpu_count"] == 2


def test_apache_reader_uses_only_fixed_systemctl_arguments(helper: dict[str, Any]) -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        stdout = "loaded\n" if "show" in argv else ""
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    result = helper["apache_facts"]("apache2.service", runner=runner)

    assert result == {"service": "apache2.service", "installed": True, "active": True}
    assert calls == [
        [
            "/usr/bin/systemctl",
            "show",
            "--property=LoadState",
            "--value",
            "apache2.service",
        ],
        ["/usr/bin/systemctl", "is-active", "--quiet", "apache2.service"],
    ]


def test_resource_reader_uses_root_and_fixed_proc_file(
    helper: dict[str, Any], tmp_path: Path
) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:       1024 kB\n", encoding="ascii")
    paths: list[str] = []

    def statvfs(path: str) -> os.statvfs_result:
        paths.append(path)
        return os.statvfs("/")

    result = helper["resource_facts"](
        statvfs=statvfs,
        meminfo_path=meminfo,
        load_reader=lambda: (0.5, 0.4, 0.3),
        cpu_reader=lambda: 2,
    )

    assert paths == ["/"]
    assert result["memory_available_bytes"] == 1024 * 1024
    assert result["logical_cpu_count"] == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["target-helper"],
        ["target-helper", "unknown"],
        ["target-helper", "version", "extra"],
        ["target-helper", ";sh"],
    ],
)
def test_main_rejects_unknown_extra_and_injection_arguments(
    helper: dict[str, Any], monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0)

    with pytest.raises(helper["HelperFailure"]):
        helper["main"](argv)


def test_direct_non_root_execution_is_refused() -> None:
    if os.geteuid() == 0:
        pytest.skip("host test requires an unprivileged caller")
    result = subprocess.run(
        [str(HELPER_PATH), "version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 4
    assert result.stderr.strip() == "root_required"
    assert result.stdout == ""
