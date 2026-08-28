"""Tests for typed environment configuration."""

import os
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from chaos_agent.config import (
    Environment,
    LocalAccessFileError,
    LocalFileIssue,
    LogFormat,
    LogLevel,
    Settings,
    TargetConfigurationRequired,
    validate_access_files,
)
from chaos_agent.domain.target import ApacheService

TARGET_ID = "8d047f58-0dc7-4d61-a165-82b02edbc2c8"


def complete_target_values(tmp_path: Path) -> dict[str, object]:
    return {
        "target_id": TARGET_ID,
        "target_host": "dev-web.internal",
        "site_health_url": "https://dev-web.internal/health",
        "ssh_private_key_path": tmp_path / "id_ed25519",
        "ssh_known_hosts_path": tmp_path / "known_hosts",
    }


def test_settings_have_safe_phase_one_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.agent_id == "chaos-agent-dev"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.data_dir == Path("/var/lib/chaos-agent")
    assert settings.log_level is LogLevel.INFO
    assert settings.log_format is LogFormat.JSON
    assert settings.heartbeat_interval_seconds == 10
    assert settings.heartbeat_max_age_seconds == 30
    assert settings.target_configured is False


def test_unconfigured_settings_refuse_target_access() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(TargetConfigurationRequired, match="not configured"):
        settings.require_target_access()


def test_settings_load_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_AGENT_ID", "foundation-test")
    monkeypatch.setenv("CHAOS_DATA_DIR", "/var/lib/chaos-agent-test")
    monkeypatch.setenv("CHAOS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("CHAOS_LOG_FORMAT", "console")
    monkeypatch.setenv("CHAOS_HEARTBEAT_INTERVAL_SECONDS", "20")
    monkeypatch.setenv("CHAOS_HEARTBEAT_MAX_AGE_SECONDS", "45")

    settings = Settings(_env_file=None)

    assert settings.agent_id == "foundation-test"
    assert settings.data_dir == Path("/var/lib/chaos-agent-test")
    assert settings.log_level is LogLevel.DEBUG
    assert settings.log_format is LogFormat.CONSOLE
    assert settings.heartbeat_interval_seconds == 20
    assert settings.heartbeat_max_age_seconds == 45


@pytest.mark.parametrize(
    "unsafe_path",
    [
        ".",
        "relative/data",
        "/",
        "/home",
        "/home/chaos-agent",
        "/Users/developer",
        "/root",
        "/root/.ssh",
        "/run/secrets/chaos-agent/ssh",
        "/run/secrets/chaos-agent/ssh/nested",
    ],
)
def test_settings_reject_unsafe_data_directories(unsafe_path: str) -> None:
    with pytest.raises(ValidationError):
        Settings(data_dir=unsafe_path, _env_file=None)


def test_settings_reject_invalid_agent_id() -> None:
    with pytest.raises(ValidationError):
        Settings(agent_id="Agent ID With Spaces", _env_file=None)


def test_settings_reject_unsupported_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)


def test_settings_reject_unknown_log_values() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="TRACE", log_format="xml", _env_file=None)


def test_settings_reject_heartbeat_max_age_without_tolerance() -> None:
    with pytest.raises(ValidationError, match="at least twice"):
        Settings(
            heartbeat_interval_seconds=20,
            heartbeat_max_age_seconds=39,
            _env_file=None,
        )


def test_complete_target_group_resolves_typed_access_config(tmp_path: Path) -> None:
    settings = Settings(**complete_target_values(tmp_path), _env_file=None)

    target = settings.require_target_access()

    assert settings.target_configured is True
    assert target.target_id == UUID(TARGET_ID)
    assert target.target_host == "dev-web.internal"
    assert target.target_port == 22
    assert target.target_user == "chaos-agent"
    assert target.apache_service is ApacheService.APACHE2
    assert str(target.site_health_url) == "https://dev-web.internal/health"


def test_target_group_loads_from_prefixed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHAOS_TARGET_ID", TARGET_ID)
    monkeypatch.setenv("CHAOS_TARGET_HOST", "192.0.2.10")
    monkeypatch.setenv("CHAOS_SITE_HEALTH_URL", "http://192.0.2.10/status")
    monkeypatch.setenv("CHAOS_SSH_PRIVATE_KEY_PATH", str(tmp_path / "id_ed25519"))
    monkeypatch.setenv("CHAOS_SSH_KNOWN_HOSTS_PATH", str(tmp_path / "known_hosts"))

    target = Settings(_env_file=None).require_target_access()

    assert target.target_id == UUID(TARGET_ID)
    assert target.target_host == "192.0.2.10"
    assert str(target.site_health_url) == "http://192.0.2.10/status"


@pytest.mark.parametrize("missing", ["target_id", "target_host", "site_health_url"])
def test_settings_reject_incomplete_target_group(tmp_path: Path, missing: str) -> None:
    values = complete_target_values(tmp_path)
    del values[missing]

    with pytest.raises(ValidationError, match="must be configured together"):
        Settings(**values, _env_file=None)


@pytest.mark.parametrize(
    "target_host",
    [
        "-oProxyCommand=bad",
        "user@host",
        "ssh://dev-web.internal",
        "dev-web.internal:22",
        " dev-web.internal",
        "bad..host",
        "bad_host",
        "[2001:db8::1]",
        "fe80::1%eth0",
    ],
)
def test_settings_reject_unsafe_target_hosts(tmp_path: Path, target_host: str) -> None:
    values = complete_target_values(tmp_path)
    values["target_host"] = target_host

    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)


@pytest.mark.parametrize("target_host", ["127.0.0.1", "2001:db8::1", "dev-web.internal"])
def test_settings_accept_dns_and_ip_target_hosts(tmp_path: Path, target_host: str) -> None:
    values = complete_target_values(tmp_path)
    values["target_host"] = target_host

    assert Settings(**values, _env_file=None).target_host == target_host


def test_settings_reject_root_target_user(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must not be root"):
        Settings(**complete_target_values(tmp_path), target_user="root", _env_file=None)


@pytest.mark.parametrize("service", ["nginx.service", "apache2", "httpd"])
def test_settings_reject_unsupported_apache_service(tmp_path: Path, service: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            **complete_target_values(tmp_path),
            target_apache_service=service,
            _env_file=None,
        )


@pytest.mark.parametrize(
    "url",
    [
        "ftp://dev-web.internal/",
        "https://user:password@dev-web.internal/",
        "https://dev-web.internal/#fragment",
    ],
)
def test_settings_reject_unsafe_site_urls(tmp_path: Path, url: str) -> None:
    values = complete_target_values(tmp_path)
    values["site_health_url"] = url

    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)


def test_settings_reject_nonprintable_expected_content(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="printable"):
        Settings(
            **complete_target_values(tmp_path),
            site_expected_content="healthy\nsecret",
            _env_file=None,
        )


def test_settings_reject_invalid_ssh_timeout_order(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must exceed"):
        Settings(
            **complete_target_values(tmp_path),
            ssh_connect_timeout_seconds=10,
            ssh_command_timeout_seconds=10,
            _env_file=None,
        )


def test_settings_reject_overlapping_ssh_paths(tmp_path: Path) -> None:
    same_path = tmp_path / "material"
    values = complete_target_values(tmp_path)
    values["ssh_private_key_path"] = same_path
    values["ssh_known_hosts_path"] = same_path

    with pytest.raises(ValidationError, match="must be different"):
        Settings(**values, _env_file=None)


def test_settings_reject_access_files_in_data_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    values = complete_target_values(tmp_path)
    values["ssh_private_key_path"] = data_dir / "id_ed25519"

    with pytest.raises(ValidationError, match="application data directory"):
        Settings(**values, data_dir=data_dir, _env_file=None)


@pytest.mark.parametrize(
    "setting,path",
    [
        ("ssh_private_key_path", "relative/id_ed25519"),
        ("ssh_known_hosts_path", "/opt/chaos-agent/known_hosts"),
        ("site_ca_bundle_path", "/opt/chaos-agent/ca.pem"),
    ],
)
def test_settings_reject_unsafe_control_file_paths(tmp_path: Path, setting: str, path: str) -> None:
    values = complete_target_values(tmp_path)
    values[setting] = path

    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)


def write_safe_access_files(tmp_path: Path) -> Settings:
    values = complete_target_values(tmp_path)
    private_key = Path(values["ssh_private_key_path"])
    known_hosts = Path(values["ssh_known_hosts_path"])
    private_key.write_text("synthetic-private-key", encoding="utf-8")
    known_hosts.write_text("dev-web.internal synthetic-host-key", encoding="utf-8")
    private_key.chmod(0o600)
    known_hosts.chmod(0o644)
    return Settings(**values, _env_file=None)


def test_access_file_validation_accepts_safe_regular_files(tmp_path: Path) -> None:
    settings = write_safe_access_files(tmp_path)

    validate_access_files(settings.require_target_access())


@pytest.mark.parametrize(
    "filename,expected_setting",
    [("id_ed25519", "ssh_private_key_path"), ("known_hosts", "ssh_known_hosts_path")],
)
def test_access_file_validation_rejects_missing_files(
    tmp_path: Path, filename: str, expected_setting: str
) -> None:
    settings = write_safe_access_files(tmp_path)
    (tmp_path / filename).unlink()

    with pytest.raises(LocalAccessFileError) as captured:
        validate_access_files(settings.require_target_access())

    assert captured.value.setting == expected_setting
    assert captured.value.issue is LocalFileIssue.MISSING
    assert "synthetic" not in str(captured.value)


def test_access_file_validation_rejects_symlink(tmp_path: Path) -> None:
    settings = write_safe_access_files(tmp_path)
    private_key = tmp_path / "id_ed25519"
    private_key.unlink()
    private_key.symlink_to(tmp_path / "known_hosts")

    with pytest.raises(LocalAccessFileError) as captured:
        validate_access_files(settings.require_target_access())

    assert captured.value.issue is LocalFileIssue.SYMLINK


def test_access_file_validation_rejects_empty_file(tmp_path: Path) -> None:
    settings = write_safe_access_files(tmp_path)
    (tmp_path / "known_hosts").write_text("", encoding="utf-8")

    with pytest.raises(LocalAccessFileError) as captured:
        validate_access_files(settings.require_target_access())

    assert captured.value.issue is LocalFileIssue.EMPTY


def test_access_file_validation_rejects_directory(tmp_path: Path) -> None:
    values = complete_target_values(tmp_path)
    private_key = Path(values["ssh_private_key_path"])
    private_key.mkdir()
    known_hosts = Path(values["ssh_known_hosts_path"])
    known_hosts.write_text("synthetic-host-key", encoding="utf-8")
    known_hosts.chmod(0o644)
    settings = Settings(**values, _env_file=None)

    with pytest.raises(LocalAccessFileError) as captured:
        validate_access_files(settings.require_target_access())

    assert captured.value.issue is LocalFileIssue.NOT_REGULAR


def test_access_file_validation_checks_optional_ca_bundle(tmp_path: Path) -> None:
    write_safe_access_files(tmp_path)
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("synthetic-ca", encoding="utf-8")
    ca_bundle.chmod(0o666)
    configured = Settings(
        **complete_target_values(tmp_path),
        site_ca_bundle_path=ca_bundle,
        _env_file=None,
    )

    with pytest.raises(LocalAccessFileError) as captured:
        validate_access_files(configured.require_target_access())

    assert captured.value.setting == "site_ca_bundle_path"
    assert captured.value.issue is LocalFileIssue.UNSAFE_MODE


@pytest.mark.parametrize(
    "filename,mode",
    [("id_ed25519", 0o640), ("known_hosts", 0o666)],
)
def test_access_file_validation_rejects_unsafe_modes(
    tmp_path: Path, filename: str, mode: int
) -> None:
    settings = write_safe_access_files(tmp_path)
    os.chmod(tmp_path / filename, mode)

    with pytest.raises(LocalAccessFileError) as captured:
        validate_access_files(settings.require_target_access())

    assert captured.value.issue is LocalFileIssue.UNSAFE_MODE
