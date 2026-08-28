"""Typed, environment-based configuration for Chaos Agent."""

import ipaddress
import os
import stat
from decimal import Decimal
from enum import StrEnum
from os import path as os_path
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator
from pydantic.functional_validators import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from chaos_agent.domain.target import ApacheService

DEFAULT_SSH_PRIVATE_KEY_PATH = Path("/run/secrets/chaos-agent/ssh/id_ed25519")
DEFAULT_SSH_KNOWN_HOSTS_PATH = Path("/run/secrets/chaos-agent/ssh/known_hosts")
DEPLOYED_SOURCE_ROOT = Path("/opt/chaos-agent")


class Environment(StrEnum):
    """Deployment environments supported by the current phase."""

    DEVELOPMENT = "development"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    """Supported application log renderings."""

    JSON = "json"
    CONSOLE = "console"


class TargetConfigurationRequired(ValueError):
    """A remote preflight was requested without a complete target group."""


class LocalFileIssue(StrEnum):
    """Safe classifications for local credential and CA file failures."""

    MISSING = "missing"
    SYMLINK = "symlink"
    NOT_REGULAR = "not_regular"
    EMPTY = "empty"
    UNREADABLE = "unreadable"
    UNSAFE_MODE = "unsafe_mode"


class LocalAccessFileError(ValueError):
    """A safe local-file validation error that never includes file contents."""

    def __init__(self, setting: str, issue: LocalFileIssue) -> None:
        self.setting = setting
        self.issue = issue
        super().__init__(f"{setting} is {issue.value}")


class TargetAccessConfig(BaseModel):
    """Resolved configuration required for one remote target preflight."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: UUID
    target_host: str
    target_port: int
    target_user: str
    ssh_private_key_path: Path
    ssh_known_hosts_path: Path
    ssh_connect_timeout_seconds: int
    ssh_command_timeout_seconds: int
    apache_service: ApacheService
    min_root_free_mib: int
    min_memory_available_mib: int
    max_load_per_cpu: Decimal
    site_health_url: AnyHttpUrl
    site_expected_status: int
    site_expected_content: str | None
    site_timeout_seconds: Decimal
    site_max_response_bytes: int
    site_ca_bundle_path: Path | None


class Settings(BaseSettings):
    """Validated settings loaded from ``CHAOS_`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CHAOS_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    agent_id: str = Field(
        default="chaos-agent-dev",
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$",
    )
    environment: Environment = Environment.DEVELOPMENT
    data_dir: Path = Path("/var/lib/chaos-agent")
    log_level: LogLevel = LogLevel.INFO
    log_format: LogFormat = LogFormat.JSON
    heartbeat_interval_seconds: int = Field(default=10, ge=1, le=300)
    heartbeat_max_age_seconds: int = Field(default=30, ge=2, le=900)

    target_id: UUID | None = None
    target_host: str | None = None
    target_port: int = Field(default=22, ge=1, le=65535)
    target_user: str = Field(
        default="chaos-agent",
        min_length=1,
        max_length=32,
        pattern=r"^[a-z_][a-z0-9_-]*$",
    )
    ssh_private_key_path: Path = DEFAULT_SSH_PRIVATE_KEY_PATH
    ssh_known_hosts_path: Path = DEFAULT_SSH_KNOWN_HOSTS_PATH
    ssh_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    ssh_command_timeout_seconds: int = Field(default=15, ge=2, le=60)

    target_apache_service: ApacheService = ApacheService.APACHE2
    preflight_min_root_free_mib: int = Field(default=1024, ge=128, le=1_048_576)
    preflight_min_memory_available_mib: int = Field(default=256, ge=64, le=1_048_576)
    preflight_max_load_per_cpu: Decimal = Field(default=Decimal("1.50"), gt=0, le=10)

    site_health_url: AnyHttpUrl | None = None
    site_expected_status: int = Field(default=200, ge=100, le=599)
    site_expected_content: str | None = Field(default=None, min_length=1, max_length=128)
    site_timeout_seconds: Decimal = Field(default=Decimal("5"), gt=0, le=30)
    site_max_response_bytes: int = Field(default=65_536, ge=1024, le=1_048_576)
    site_ca_bundle_path: Path | None = None

    @field_validator("data_dir")
    @classmethod
    def validate_data_dir(cls, data_dir: Path) -> Path:
        """Reject relative, overly broad, home, and SSH-material paths."""
        if not data_dir.is_absolute():
            raise ValueError("data directory must be an absolute path")

        normalized = Path(os_path.normpath(data_dir))
        broad_paths = {
            Path("/"),
            Path("/home"),
            Path("/Users"),
            Path("/root"),
            Path.home(),
        }
        if normalized in broad_paths or normalized.parent in {Path("/home"), Path("/Users")}:
            raise ValueError("data directory must not be a root or home directory")

        ssh_paths = {
            Path.home() / ".ssh",
            Path("/root/.ssh"),
            Path("/run/secrets/chaos-agent/ssh"),
        }
        if any(normalized == path or normalized.is_relative_to(path) for path in ssh_paths):
            raise ValueError("data directory must not use an SSH-material path")

        return normalized

    @field_validator("target_host")
    @classmethod
    def validate_target_host(cls, target_host: str | None) -> str | None:
        """Accept a plain DNS name or IP address, never URI or option syntax."""
        if target_host is None:
            return None
        if target_host != target_host.strip() or not target_host:
            raise ValueError("target host must not be empty or contain surrounding whitespace")
        if target_host.startswith("-") or any(
            token in target_host for token in ("@", "/", "[", "]", "%", "://")
        ):
            raise ValueError("target host must be a plain DNS name or IP address")

        try:
            ipaddress.ip_address(target_host)
        except ValueError:
            if len(target_host) > 253:
                raise ValueError("target host is too long") from None
            labels = target_host.rstrip(".").split(".")
            if any(
                not label
                or len(label) > 63
                or not label[0].isalnum()
                or not label[-1].isalnum()
                or any(not (character.isalnum() or character == "-") for character in label)
                for label in labels
            ):
                raise ValueError("target host must be a valid DNS name or IP address") from None
        return target_host

    @field_validator("target_user")
    @classmethod
    def validate_target_user(cls, target_user: str) -> str:
        if target_user == "root":
            raise ValueError("target user must not be root")
        return target_user

    @field_validator("ssh_private_key_path", "ssh_known_hosts_path")
    @classmethod
    def validate_ssh_path(cls, path: Path) -> Path:
        return _validate_control_file_path(path, "SSH material")

    @field_validator("site_ca_bundle_path")
    @classmethod
    def validate_ca_bundle_path(cls, path: Path | None) -> Path | None:
        if path is None:
            return None
        return _validate_control_file_path(path, "CA bundle")

    @field_validator("site_health_url")
    @classmethod
    def validate_site_health_url(cls, url: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if url is None:
            return None
        if url.username is not None or url.password is not None:
            raise ValueError("site health URL must not contain user information")
        if url.fragment is not None:
            raise ValueError("site health URL must not contain a fragment")
        return url

    @field_validator("site_expected_content")
    @classmethod
    def validate_expected_content(cls, content: str | None) -> str | None:
        if content is not None and not content.isprintable():
            raise ValueError("expected site content must contain printable characters only")
        return content

    @model_validator(mode="after")
    def validate_heartbeat_timing(self) -> "Settings":
        """Leave enough tolerance for a delayed heartbeat update."""
        if self.heartbeat_max_age_seconds < self.heartbeat_interval_seconds * 2:
            raise ValueError("heartbeat maximum age must be at least twice the heartbeat interval")

        target_group = (
            self.target_id is not None,
            self.target_host is not None,
            self.site_health_url is not None,
        )
        if any(target_group) and not all(target_group):
            raise ValueError(
                "target ID, target host, and site health URL must be configured together"
            )
        if self.ssh_private_key_path == self.ssh_known_hosts_path:
            raise ValueError("SSH private key and known-hosts paths must be different")
        if self.ssh_command_timeout_seconds <= self.ssh_connect_timeout_seconds:
            raise ValueError("SSH command timeout must exceed SSH connect timeout")

        access_paths = [self.ssh_private_key_path, self.ssh_known_hosts_path]
        if self.site_ca_bundle_path is not None:
            access_paths.append(self.site_ca_bundle_path)
        if any(
            path == self.data_dir or path.is_relative_to(self.data_dir) for path in access_paths
        ):
            raise ValueError(
                "SSH material and CA bundle must not use the application data directory"
            )
        return self

    @property
    def target_configured(self) -> bool:
        """Return whether the complete optional target group is configured."""
        return self.target_id is not None

    def require_target_access(self) -> TargetAccessConfig:
        """Return resolved target settings or refuse an unconfigured preflight."""
        if self.target_id is None or self.target_host is None or self.site_health_url is None:
            raise TargetConfigurationRequired("target access is not configured")
        return TargetAccessConfig(
            target_id=self.target_id,
            target_host=self.target_host,
            target_port=self.target_port,
            target_user=self.target_user,
            ssh_private_key_path=self.ssh_private_key_path,
            ssh_known_hosts_path=self.ssh_known_hosts_path,
            ssh_connect_timeout_seconds=self.ssh_connect_timeout_seconds,
            ssh_command_timeout_seconds=self.ssh_command_timeout_seconds,
            apache_service=self.target_apache_service,
            min_root_free_mib=self.preflight_min_root_free_mib,
            min_memory_available_mib=self.preflight_min_memory_available_mib,
            max_load_per_cpu=self.preflight_max_load_per_cpu,
            site_health_url=self.site_health_url,
            site_expected_status=self.site_expected_status,
            site_expected_content=self.site_expected_content,
            site_timeout_seconds=self.site_timeout_seconds,
            site_max_response_bytes=self.site_max_response_bytes,
            site_ca_bundle_path=self.site_ca_bundle_path,
        )


def load_settings() -> Settings:
    """Load settings from the process environment."""
    return Settings()


def validate_access_files(config: TargetAccessConfig) -> None:
    """Validate local SSH and optional CA files without reading their contents."""
    _validate_local_file(
        config.ssh_private_key_path,
        "ssh_private_key_path",
        forbidden_mode_bits=0o077,
    )
    _validate_local_file(
        config.ssh_known_hosts_path,
        "ssh_known_hosts_path",
        forbidden_mode_bits=0o022,
    )
    if config.site_ca_bundle_path is not None:
        _validate_local_file(
            config.site_ca_bundle_path,
            "site_ca_bundle_path",
            forbidden_mode_bits=0o022,
        )


def _validate_control_file_path(path: Path, label: Literal["SSH material", "CA bundle"]) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    normalized = Path(os_path.normpath(path))
    if normalized == Path("/"):
        raise ValueError(f"{label} path must identify a file")
    home = Path.home()
    if normalized == home or normalized.is_relative_to(home):
        raise ValueError(f"{label} path must not use a home directory")
    if normalized == DEPLOYED_SOURCE_ROOT or normalized.is_relative_to(DEPLOYED_SOURCE_ROOT):
        raise ValueError(f"{label} path must not use the deployed source directory")
    return normalized


def _validate_local_file(path: Path, setting: str, *, forbidden_mode_bits: int) -> None:
    try:
        file_status = path.lstat()
    except FileNotFoundError as error:
        raise LocalAccessFileError(setting, LocalFileIssue.MISSING) from error
    except OSError as error:
        raise LocalAccessFileError(setting, LocalFileIssue.UNREADABLE) from error

    if stat.S_ISLNK(file_status.st_mode):
        raise LocalAccessFileError(setting, LocalFileIssue.SYMLINK)
    if not stat.S_ISREG(file_status.st_mode):
        raise LocalAccessFileError(setting, LocalFileIssue.NOT_REGULAR)
    if file_status.st_size == 0:
        raise LocalAccessFileError(setting, LocalFileIssue.EMPTY)
    if stat.S_IMODE(file_status.st_mode) & forbidden_mode_bits:
        raise LocalAccessFileError(setting, LocalFileIssue.UNSAFE_MODE)
    if not os.access(path, os.R_OK):
        raise LocalAccessFileError(setting, LocalFileIssue.UNREADABLE)
