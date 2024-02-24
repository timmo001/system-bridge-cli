"""System Bridge CLI."""
from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import asdict
import json
import os
import subprocess
import sys
from typing import Any
from uuid import uuid4

import typer

from systembridgeconnector.websocket_client import WebSocketClient
from systembridgemodels.modules import GetData, ModulesData
from systembridgeshared.common import get_user_data_directory
from systembridgeshared.exceptions import (
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeshared.logger import setup_logger
from systembridgeshared.settings import Settings

from ._version import __version__

setup_logger("ERROR", "system-bridge-cli")
# logger = logging.getLogger()

app = typer.Typer()
settings = Settings()

loop = asyncio.new_event_loop()
modules_data = ModulesData()
websocket_client = WebSocketClient(
    "localhost",
    settings.data.api.port,
    settings.data.api.token,
)
websocket_listen_task: asyncio.Task | None = None


async def _handle_module(
    module_name: str,
    module: Any,
) -> None:
    """Handle data from the WebSocket client."""
    global modules_data  # noqa: PLW0603
    setattr(modules_data, module_name, module)


async def _listen_for_data() -> None:
    """Listen for events from the WebSocket."""
    global websocket_listen_task  # noqa: PLW0603

    try:
        await websocket_client.listen(callback=_handle_module)
    except asyncio.CancelledError:
        pass
    except (
        ConnectionErrorException,
        ConnectionClosedException,
        ConnectionResetError,
    ) as exception:
        typer.secho(f"Connection closed to WebSocket: {exception}", fg=typer.colors.RED)

    if websocket_listen_task:
        websocket_listen_task.cancel()
        websocket_listen_task = None


def _setup_listener() -> None:
    """Set up the listener for the WebSocket."""
    global websocket_listen_task  # noqa: PLW0603

    if websocket_listen_task:
        websocket_listen_task.cancel()
        websocket_listen_task = None

    if loop is None:
        typer.secho("No event loop!", fg=typer.colors.RED)
        return

    # Listen for data
    websocket_listen_task = loop.create_task(
        _listen_for_data(),
        name="System Bridge WebSocket Listener",
    )


async def _get_data_from_websocket(modules: list[str]) -> ModulesData:
    """Get data from websocket."""
    global modules_data  # noqa: PLW0603
    global websocket_listen_task  # noqa: PLW0603

    # Connect to the WebSocket
    await websocket_client.connect()

    # Run the listener in a separate thread
    with concurrent.futures.ThreadPoolExecutor() as executor:
        loop.run_in_executor(executor, _setup_listener)

    # Get data
    await websocket_client.get_data(
        GetData(
            modules=modules,
        )
    )

    # Wait for the data to be received
    while not all(getattr(modules_data, module) for module in modules):
        await asyncio.sleep(1)

    if websocket_listen_task:
        websocket_listen_task.cancel()
        websocket_listen_task = None

    # Close the WebSocket
    await websocket_client.close()

    return modules_data


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


@app.command(name="data", short_help="Get data")
def data(module: str) -> None:
    """Get data."""
    module_data = loop.run_until_complete(_get_data_from_websocket([module]))
    loop.close()

    typer.secho(json.dumps(asdict(getattr(module_data, module))), fg=typer.colors.GREEN)


@app.command(name="data-value", short_help="Get data value")
def data_value(
    module: str,
    key: str,
) -> None:
    """Get data value."""
    module_data = loop.run_until_complete(_get_data_from_websocket([module]))
    loop.close()

    if result := getattr(getattr(module_data, module), key):
        typer.secho(result, fg=typer.colors.GREEN)
    else:
        typer.secho(f"Could not find {key}", err=True, fg=typer.colors.RED)


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
