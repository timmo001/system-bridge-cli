"""System Bridge CLI."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
import subprocess
import sys
from uuid import uuid4

from tabulate import tabulate
import typer

from systembridgeshared.common import get_user_data_directory
from systembridgeshared.settings import Settings

from ._version import __version__

app = typer.Typer()
settings = Settings()


@app.command(name="token", short_help="Get token")
def token(reset: bool = False) -> None:
    """Get Token."""
    if reset:
        settings.data.api.token = str(uuid4())
        settings.update(asdict(settings.data))
        typer.secho(settings.data.api.token, fg=typer.colors.CYAN)
    else:
        typer.secho(settings.data.api.token, fg=typer.colors.CYAN)


@app.command(name="api-port", short_help="Get api port")
def api_port() -> None:
    """Get API Port."""
    typer.secho(settings.data.api.port, fg=typer.colors.CYAN)


# TODO: Add data commands
# @app.command(name="data", short_help="Get data")
# def data(module: str, key=None) -> None:
#     """Get data."""
#     table_module = TABLE_MAP.get(module)
#     if key:
#         result = database.get_data_by_key(table_module, key)
#     else:
#         result = database.get_data(table_module)

#     output = [item.dict() for item in result]

#     table_data = tabulate(output, headers="keys", tablefmt="psql",)
#     typer.secho(table_data, fg=typer.colors.GREEN)


# @app.command(name="data-value", short_help="Get data value")
# def data_value(
#     module: str,
#     key: str,
# ) -> None:
#     """Get data value."""
#     table_module = TABLE_MAP.get(module)
#     output = database.get_data_item_by_key(table_module, key)
#     typer.secho(output.value if output else None, fg=typer.colors.GREEN)


@app.command(name="settings", short_help="Get all settings")
def settings_all():
    """Get all Settings."""
    typer.secho(json.dumps(asdict(settings.data)), fg=typer.colors.CYAN)


@app.command(name="setting", short_help="Get setting")
def setting(key: str) -> None:
    """Get setting."""
    if key == "api":
        typer.secho(json.dumps(asdict(settings.data.api)), fg=typer.colors.CYAN)
        return

    if key.startswith("api."):
        key = key.split(".")[1]
        result = getattr(settings.data.api, key)
    else:
        result = getattr(settings.data, key)

    if result:
        typer.secho(result, fg=typer.colors.CYAN)
    else:
        typer.secho(f"Could not find {key}", err=True, fg=typer.colors.RED)


@app.command(name="path-logs", short_help="Logs path")
def path_logs() -> None:
    """Open logs path."""
    typer.secho(
        os.path.join(get_user_data_directory(), "system-bridge.log"),
        fg=typer.colors.YELLOW,
    )


@app.command(name="path-logs-backend", short_help="Backend logs path")
def path_logs_backend() -> None:
    """Open backend logs path."""
    typer.secho(
        os.path.join(get_user_data_directory(), "system-bridge-backend.log"),
        fg=typer.colors.YELLOW,
    )


@app.command(name="path-logs-gui", short_help="GUI logs path")
def path_logs_gui() -> None:
    """Open gui logs path."""
    typer.secho(
        os.path.join(get_user_data_directory(), "system-bridge-gui.log"),
        fg=typer.colors.YELLOW,
    )


@app.command(name="open-logs", short_help="Open logs")
def open_logs() -> None:
    """Open logs."""
    path = os.path.join(get_user_data_directory(), "system-bridge.log")
    if sys.platform == "win32":
        os.startfile(path)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, path])


@app.command(name="open-logs-backend", short_help="Open backend logs")
def open_logs_backend() -> None:
    """Open backend logs."""
    path = os.path.join(get_user_data_directory(), "system-bridge-backend.log")
    if sys.platform == "win32":
        os.startfile(path)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, path])


@app.command(name="open-logs-gui", short_help="Open GUI logs")
def open_logs_gui() -> None:
    """Open gui logs."""
    path = os.path.join(get_user_data_directory(), "system-bridge-gui.log")
    if sys.platform == "win32":
        os.startfile(path)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, path])


@app.command(name="version", short_help="CLI Version")
def version() -> None:
    """CLI Version."""
    typer.secho(__version__.public(), fg=typer.colors.CYAN)


if __name__ == "__main__":
    app()
