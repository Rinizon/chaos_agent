"""Typed, environment-based configuration for Chaos Agent."""

from enum import StrEnum
from os import path as os_path
from pathlib import Path

from pydantic import Field, model_validator
from pydantic.functional_validators import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class Settings(BaseSettings):
    """Validated settings loaded from ``CHAOS_`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CHAOS_",
        case_sensitive=False,
        extra="ignore",
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

    @model_validator(mode="after")
    def validate_heartbeat_timing(self) -> "Settings":
        """Leave enough tolerance for a delayed heartbeat update."""
        if self.heartbeat_max_age_seconds < self.heartbeat_interval_seconds * 2:
            raise ValueError("heartbeat maximum age must be at least twice the heartbeat interval")
        return self


def load_settings() -> Settings:
    """Load settings from the process environment."""
    return Settings()
