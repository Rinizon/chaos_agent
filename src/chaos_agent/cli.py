"""Command-line interface for Chaos Agent."""

import asyncio
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from pydantic import ValidationError
from sqlalchemy.orm import Session

from chaos_agent.adapters.http_observer import HttpxSiteObserver
from chaos_agent.adapters.openssh import OpenSshTransport
from chaos_agent.adapters.persistence.database import create_database_engine
from chaos_agent.adapters.persistence.models import Base, ExperimentRow
from chaos_agent.adapters.persistence.repositories import ExperimentRepository
from chaos_agent.application.experiments import ScenarioCatalog
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


def _experiment_session(data_dir: Path) -> Session:
    engine = create_database_engine(data_dir / "chaos-agent.db")
    Base.metadata.create_all(engine)
    return Session(engine)


def _row_payload(row: ExperimentRow) -> dict[str, object]:
    return {
        "experiment_id": row.experiment_id,
        "target_id": row.target_id,
        "target_label": row.target_label,
        "scenario": row.scenario_name,
        "scenario_version": row.scenario_version,
        "state": row.state,
        "duration_seconds": row.requested_duration_seconds,
        "expires_at": row.expires_at.isoformat(),
        "initiator": row.initiator,
    }


@app.command("list")
def list_command(json_output: Annotated[bool, typer.Option("--json")] = False) -> None:
    """List installed production scenarios."""
    scenarios = ScenarioCatalog().list()
    typer.echo(
        json.dumps({"schema_version": 1, "scenarios": scenarios}, separators=(",", ":"))
        if json_output
        else "No production scenarios are installed."
    )


@app.command("run")
def run_command(
    scenario: str,
    initiator: Annotated[str, typer.Option("--initiator")],
    duration: Annotated[int | None, typer.Option("--duration")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Schedule an installed scenario; Phase 3 intentionally has none."""
    if not ScenarioCatalog().contains(scenario):
        payload = {"schema_version": 1, "outcome": "refused", "category": "scenario_unavailable"}
        typer.echo(
            json.dumps(payload, separators=(",", ":"))
            if json_output
            else "Scenario is unavailable."
        )
        raise typer.Exit(code=1)
    raise typer.Exit(code=1)


@app.command("status")
def status_command(
    experiment_id: str | None = None, json_output: Annotated[bool, typer.Option("--json")] = False
) -> None:
    """Show an experiment or the currently active experiment."""
    settings = load_settings()
    with _experiment_session(settings.data_dir) as session:
        repository = ExperimentRepository(session)
        row = repository.get(experiment_id) if experiment_id else next(
            iter(repository.list_active()), None
        )
        if row is None:
            raise typer.Exit(code=1)
        payload = _row_payload(row)
    typer.echo(
        json.dumps(payload, separators=(",", ":"))
        if json_output
        else f"{payload['experiment_id']}: {payload['state']}"
    )


@app.command("history")
def history_command(
    scenario: str | None = None,
    state: str | None = None,
    limit: int = 100,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List bounded experiment history."""
    settings = load_settings()
    with _experiment_session(settings.data_dir) as session:
        rows = [
            _row_payload(row)
            for row in ExperimentRepository(session).list_history(
                scenario=scenario, state=state, limit=limit
            )
        ]
    typer.echo(
        json.dumps({"schema_version": 1, "experiments": rows}, separators=(",", ":"))
        if json_output
        else "\n".join(f"{r['experiment_id']}: {r['state']}" for r in rows)
    )


@app.command("abort")
def abort_command(
    experiment_id: str,
    initiator: Annotated[str, typer.Option("--initiator")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Durably request cancellation; cleanup is performed by the supervisor."""
    settings = load_settings()
    with _experiment_session(settings.data_dir) as session:
        accepted = ExperimentRepository(session).request_control(
            experiment_id, "cancel", initiator, f"cancel:{experiment_id}:{initiator}"
        )
        session.commit()
    payload = {
        "schema_version": 1,
        "accepted": accepted,
        "experiment_id": experiment_id,
        "request": "cancel",
    }
    typer.echo(
        json.dumps(payload, separators=(",", ":"))
        if json_output
        else ("Cancellation requested." if accepted else "Cancellation was already requested.")
    )


@app.command("reconcile")
def reconcile_command(
    experiment_id: str | None = None,
    initiator: Annotated[str, typer.Option("--initiator")] = "operator",
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Durably request supervisor reconciliation."""
    settings = load_settings()
    with _experiment_session(settings.data_dir) as session:
        rows = (
            ExperimentRepository(session).list_active()
            if experiment_id is None
            else [ExperimentRepository(session).get(experiment_id)]
        )
        accepted = 0
        for row in rows:
            if row and ExperimentRepository(session).request_control(
                row.experiment_id,
                "reconcile",
                initiator,
                f"reconcile:{row.experiment_id}:{initiator}",
            ):
                accepted += 1
        session.commit()
    payload = {"schema_version": 1, "accepted": accepted}
    typer.echo(
        json.dumps(payload, separators=(",", ":"))
        if json_output
        else f"Reconciliation requested for {accepted} experiment(s)."
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
