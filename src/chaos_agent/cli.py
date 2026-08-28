"""Command-line interface for Chaos Agent."""

import json
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer
from pydantic import ValidationError

from chaos_agent.config import load_settings
from chaos_agent.logging import sanitize_text

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
