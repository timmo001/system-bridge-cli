"""System Bridge CLI."""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import asdict, is_dataclass
import json
import os
import subprocess
import sys
from typing import Any
from uuid import uuid4

import aiohttp
import typer

from systembridgecli._version import __version__
from systembridgeconnector.exceptions import (
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.websocket_client import WebSocketClient
from systembridgemodels.modules import GetData, ModulesData
from systembridgeshared.common import get_user_data_directory
from systembridgeshared.logger import setup_logger
from systembridgeshared.settings import Settings

setup_logger("ERROR", "system-bridge-cli")

app = typer.Typer()
settings = Settings()

loop = asyncio.new_event_loop()


class WebsocketData:
    """Websocket data."""

    def __init__(self) -> None:
        """Initialize."""
        self._modules_data = ModulesData()
        self._websocket_client = WebSocketClient(
            "localhost",
            settings.data.api.port,
            settings.data.api.token,
            aiohttp.ClientSession(),
        )
        self._websocket_listen_task: asyncio.Task | None = None

    async def _handle_module(
        self,
        module_name: str,
        module: Any,
    ) -> None:
        """Handle data from the WebSocket client."""
        setattr(self._modules_data, module_name, module)

    async def _listen_for_data(self) -> None:
        """Listen for events from the WebSocket."""

        try:
            await self._websocket_client.listen(callback=self._handle_module)
        except asyncio.CancelledError:
            pass
        except (
            ConnectionErrorException,
            ConnectionClosedException,
            ConnectionResetError,
        ) as exception:
            typer.secho(
                f"Connection closed to WebSocket: {exception}", fg=typer.colors.RED
            )

        if self._websocket_listen_task:
            self._websocket_listen_task.cancel()
            self._websocket_listen_task = None

    def _setup_listener(self) -> None:
        """Set up the listener for the WebSocket."""
        if self._websocket_listen_task:
            self._websocket_listen_task.cancel()
            self._websocket_listen_task = None

        if loop is None:
            typer.secho("No event loop!", fg=typer.colors.RED)
            return

        # Listen for data
        self._websocket_listen_task = loop.create_task(
            self._listen_for_data(),
            name="System Bridge WebSocket Listener",
        )

    async def get_data_from_websocket(
        self,
        modules: list[str],
    ) -> ModulesData:
        """Get data from websocket."""
        # Connect to the WebSocket
        await self._websocket_client.connect()

        # Run the listener in a separate thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            loop.run_in_executor(executor, self._setup_listener)

        # Get data
        await self._websocket_client.get_data(
            GetData(
                modules=modules,
            )
        )

        # Wait for the data to be received
        while not all(getattr(self._modules_data, module) for module in modules):
            await asyncio.sleep(1)

        if self._websocket_listen_task:
            self._websocket_listen_task.cancel()
            self._websocket_listen_task = None

        # Close the WebSocket
        await self._websocket_client.close()

        return self._modules_data


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
    websocket_data = WebsocketData()
    modules_data = loop.run_until_complete(
        websocket_data.get_data_from_websocket([module])
    )
    loop.close()

    module_data = getattr(modules_data, module)

    typer.secho(json.dumps(asdict(module_data)), fg=typer.colors.GREEN)


@app.command(name="data-value", short_help="Get data value")
def data_value(
    module: str,
    key: str,
) -> None:
    """Get data value."""
    websocket_data = WebsocketData()
    modules_data = loop.run_until_complete(
        websocket_data.get_data_from_websocket([module])
    )
    loop.close()

    module_data = getattr(modules_data, module)

    if "." in key:
        module_keys = key.split(".")

        result = module_data
        for module_key in module_keys:
            if result := getattr(result, module_key):
                response = result
            else:
                typer.secho(f"Could not find {key}", err=True, fg=typer.colors.RED)
                return

        typer.secho(
            json.dumps(asdict(response)) if is_dataclass(response) else response,
            fg=typer.colors.GREEN,
        )
    elif result := getattr(module_data, key):
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
