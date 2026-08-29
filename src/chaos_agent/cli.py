"""Command-line interface for Chaos Agent."""

import asyncio
import json
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, NoReturn

import typer
from pydantic import ValidationError

from chaos_agent.adapters.http_observer import HttpxSiteObserver
from chaos_agent.adapters.openssh import OpenSshTransport
from chaos_agent.application.preflight import PreflightService
from chaos_agent.config import (
    Settings,
    TargetAccessConfig,
    TargetConfigurationRequired,
    load_settings,
)
from chaos_agent.domain.preflight import PreflightOutcome, PreflightReport
from chaos_agent.health import evaluate_health, unhealthy_configuration_report
from chaos_agent.logging import configure_logging, sanitize_text
from chaos_agent.runtime import run_passive_agent

PACKAGE_NAME = "chaos-agent"

app = typer.Typer(
    name="chaos",
    help="Safely coordinate controlled chaos experiments in isolated development systems.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback()
def main(ctx: typer.Context) -> None:
    """Run the Chaos Agent command-line interface."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def get_version() -> str:
    """Return the version from installed package metadata."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0+uninstalled"


@app.command("version")
def version_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return machine-readable JSON output."),
    ] = False,
) -> None:
    """Show the installed Chaos Agent version."""
    installed_version = get_version()
    if json_output:
        typer.echo(json.dumps({"version": installed_version}, separators=(",", ":")))
        return

    typer.echo(installed_version)


def _safe_validation_errors(error: ValidationError) -> list[dict[str, str]]:
    """Convert validation failures into stable output without rejected input values."""
    errors: list[dict[str, str]] = []
    for detail in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in detail["loc"]) or "settings"
        errors.append(
            {
                "field": location,
                "message": sanitize_text(detail["msg"]),
                "type": detail["type"],
            }
        )
    return errors


@app.command("config-check")
def config_check_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return machine-readable JSON output."),
    ] = False,
) -> None:
    """Validate the current non-secret application configuration."""
    try:
        settings = load_settings()
    except ValidationError as error:
        errors = _safe_validation_errors(error)
        if json_output:
            typer.echo(json.dumps({"status": "invalid", "errors": errors}, separators=(",", ":")))
        else:
            typer.echo("Configuration is invalid:")
            for detail in errors:
                typer.echo(f"- {detail['field']}: {detail['message']}")
        raise typer.Exit(code=2) from None

    if json_output:
        payload = {
            "status": "valid",
            "agent_id": settings.agent_id,
            "environment": settings.environment.value,
        }
        typer.echo(json.dumps(payload, separators=(",", ":")))
        return

    typer.echo(
        f"Configuration is valid for agent '{settings.agent_id}' in {settings.environment.value}."
    )


@app.command("agent")
def agent_command() -> None:
    """Run the passive, local-only Chaos Agent process."""
    try:
        settings = load_settings()
    except ValidationError as error:
        typer.echo("Configuration is invalid:")
        for detail in _safe_validation_errors(error):
            typer.echo(f"- {detail['field']}: {detail['message']}")
        raise typer.Exit(code=2) from None

    logger = configure_logging(settings)
    exit_code = run_passive_agent(settings, logger)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command("health")
def health_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return machine-readable JSON output."),
    ] = False,
) -> None:
    """Check only the local agent runtime and its required local storage."""
    try:
        settings = load_settings()
    except ValidationError:
        payload = unhealthy_configuration_report()
        if json_output:
            typer.echo(json.dumps(payload, separators=(",", ":")))
        else:
            typer.echo("Agent health: unhealthy")
            typer.echo("- configuration: fail (configuration is invalid)")
        raise typer.Exit(code=1) from None

    report = evaluate_health(settings)
    if json_output:
        typer.echo(json.dumps(report.to_dict(), separators=(",", ":")))
    else:
        typer.echo(f"Agent health: {report.status.value}")
        for check in report.checks:
            typer.echo(f"- {check.name}: {check.status.value} ({check.message})")

    if report.status.value != "healthy":
        raise typer.Exit(code=1)


def _configuration_failure(json_output: bool, errors: list[dict[str, str]]) -> NoReturn:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "outcome": "configuration_error",
                    "category": "configuration_invalid",
                    "errors": errors,
                },
                separators=(",", ":"),
            )
        )
    else:
        typer.echo("Target preflight configuration is invalid:")
        for detail in errors:
            typer.echo(f"- {detail['field']}: {detail['message']}")
    raise typer.Exit(code=2)


async def _execute_preflight(
    config: TargetAccessConfig,
    settings: Settings,
) -> PreflightReport:
    logger = configure_logging(settings)
    service = PreflightService(OpenSshTransport(), HttpxSiteObserver(), logger=logger)
    return await service.run(config)


def _render_preflight(report: PreflightReport, json_output: bool) -> None:
    if json_output:
        typer.echo(report.model_dump_json())
        return
    typer.echo(f"Target preflight: {report.outcome.value}")
    typer.echo(f"Target: {report.target_label}")
    if report.category is not None:
        typer.echo(f"Category: {report.category}")
    for check in report.checks:
        typer.echo(f"- {check.name}: {check.status.value} ({check.message})")


@app.command("preflight")
def preflight_command(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return machine-readable JSON output."),
    ] = False,
) -> None:
    """Run the read-only target and website safety preflight."""
    try:
        settings = load_settings()
    except ValidationError as error:
        _configuration_failure(json_output, _safe_validation_errors(error))
    try:
        config = settings.require_target_access()
    except TargetConfigurationRequired:
        _configuration_failure(
            json_output,
            [
                {
                    "field": "target",
                    "message": "target access is not configured",
                    "type": "target_configuration_required",
                }
            ],
        )

    try:
        report = asyncio.run(_execute_preflight(config, settings))
    except Exception:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "schema_version": 1,
                        "outcome": "error",
                        "category": "internal_execution_error",
                    },
                    separators=(",", ":"),
                )
            )
        else:
            typer.echo("Target preflight: error")
            typer.echo("Category: internal_execution_error")
        raise typer.Exit(code=3) from None

    _render_preflight(report, json_output)
    if report.outcome is PreflightOutcome.REFUSED:
        raise typer.Exit(code=1)
    if report.outcome is PreflightOutcome.ERROR:
        local_file_error = report.category is not None and report.category.startswith(
            ("ssh_private_key_path_", "ssh_known_hosts_path_", "site_ca_bundle_path_")
        )
        raise typer.Exit(code=2 if local_file_error else 3)
