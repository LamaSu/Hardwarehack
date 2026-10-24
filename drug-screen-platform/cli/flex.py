"""
`flex`: talk to the Opentrons Flex.

    uv run flex health --host 192.168.0.42
    uv run flex snapshot --tag before --plate "Example screen"
    uv run flex run runs/example-screen/protocol.py --plate "Example screen"
    uv run flex demo plate.json          # check → protocol → simulate → before → run → after

Every command takes --host/--port (or FLEX_HOST/FLEX_PORT) and --mock.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

import run_store
from cli.common import friendly_errors
from cli.plate import build_protocol
from flex_client import FlexClient, MockFlexClient, client_from_env
from plate_layout import PlateLayout
from simulation import simulate_protocol

app = typer.Typer(help="Drive the Opentrons Flex: health, camera, runs.", no_args_is_help=True)

Host = Annotated[Optional[str], typer.Option(help="Robot IP (default: $FLEX_HOST)")]
Port = Annotated[Optional[int], typer.Option(help="Robot port (default: $FLEX_PORT or 31950)")]
Mock = Annotated[bool, typer.Option("--mock", help="Use a pretend robot")]
PlateName = Annotated[str, typer.Option("--plate", help="Plate name (selects runs/<plate>/)")]


def _client(host: Optional[str], port: Optional[int], mock: bool) -> FlexClient | MockFlexClient:
    return client_from_env(mock=mock, host=host, port=port)


def _snapshot(client, plate: str, tag: str) -> Path:
    path = run_store.RunStore().write_file(plate, f"{tag}.jpg", client.snapshot())
    typer.echo(f"Snapshot {tag}: {path}")
    return path


def _run(client, protocol_file: Path, plate: str, wait: bool) -> dict:
    store = run_store.RunStore()
    protocol_id = client.upload_protocol(protocol_file)
    run_id = client.create_run(protocol_id)
    info = {"run_id": run_id, "protocol_id": protocol_id, "robot": f"{client.host}:{client.port}",
            "started": datetime.now().isoformat(timespec="seconds"), "status": "running"}
    store.save_run_info(plate, info)
    client.action(run_id, "play")
    typer.echo(f"Run {run_id} started")
    if not wait:
        return info
    last = {"status": None}

    def progress(data: dict) -> None:
        if data.get("status") != last["status"]:
            last["status"] = data.get("status")
            typer.echo(f"  status: {last['status']}")

    final = client.wait_until_done(run_id, on_progress=progress)
    info.update(status=final.get("status"), finished=datetime.now().isoformat(timespec="seconds"),
                errors=[e.get("detail", str(e)) for e in final.get("errors", [])])
    store.save_run_info(plate, info)
    return info


@app.command()
@friendly_errors
def health(host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Check the robot is reachable and print its name and software."""
    data = _client(host, port, mock).health()
    typer.echo(f"{data.get('name')} ({data.get('robot_model')}), software {data.get('api_version')}")


@app.command()
@friendly_errors
def snapshot(plate: PlateName,
             tag: Annotated[str, typer.Option(help="before or after")] = "before",
             host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Take a deck camera picture into runs/<plate>/<tag>.jpg."""
    _snapshot(_client(host, port, mock), plate, tag)


@app.command()
@friendly_errors
def run(protocol_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)], plate: PlateName,
        wait: Annotated[bool, typer.Option(help="Follow the run until it ends")] = True,
        host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Upload a protocol, start it and (by default) follow it to the end."""
    info = _run(_client(host, port, mock), protocol_file, plate, wait)
    if info["status"] not in ("succeeded", "running"):
        raise typer.Exit(1)


@app.command()
@friendly_errors
def status(run_id: str, host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Print a run's status."""
    data = _client(host, port, mock).run_status(run_id)
    typer.echo(f"{run_id}: {data.get('status')}")


@app.command()
@friendly_errors
def pause(run_id: str, host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Pause a run."""
    _client(host, port, mock).action(run_id, "pause")
    typer.echo(f"{run_id}: pause requested")


@app.command()
@friendly_errors
def stop(run_id: str, host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Stop a run."""
    _client(host, port, mock).action(run_id, "stop")
    typer.echo(f"{run_id}: stop requested")


@app.command()
@friendly_errors
def demo(layout_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
         host: Host = None, port: Port = None, mock: Mock = False) -> None:
    """Check, generate, simulate, snapshot before, run, snapshot after."""
    client = _client(host, port, mock)
    layout = PlateLayout.load_json(layout_file)
    typer.echo(f"Robot: {client.health().get('name')}")
    protocol_file = build_protocol(layout)
    simulation = simulate_protocol(protocol_file.read_text(encoding="utf-8"))
    if not simulation.ok:
        typer.echo(f"Simulation FAILED: {simulation.error}")
        raise typer.Exit(1)
    typer.echo(f"Simulation OK: {simulation.steps} steps")
    _snapshot(client, layout.name, "before")
    info = _run(client, protocol_file, layout.name, wait=True)
    _snapshot(client, layout.name, "after")
    typer.echo(f"Run {info['status']}. Files in {run_store.RunStore().folder(layout.name)}")
    if info["status"] != "succeeded":
        raise typer.Exit(1)
