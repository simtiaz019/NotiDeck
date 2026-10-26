import logging
import multiprocessing
import os
from pathlib import Path

import typer
import uvicorn

from notideck import __version__
from notideck.config import Config
from notideck.database import engine_for, migrate, schema_current

app = typer.Typer(no_args_is_help=True, invoke_without_command=True)
db_app = typer.Typer()
app.add_typer(db_app, name="db")


def logs():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@app.callback()
def main(version: bool = typer.Option(False, "--version", is_eager=True)):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


def embedded(directory):
    from notideck.worker import run

    run(Config(directory))


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    config: Path | None = None,
    embedded_worker: bool = typer.Option(False, "--embedded-worker"),
):
    """Start Console and API. Embedded worker requires completed setup; restart after setup."""
    from notideck.api import create_app

    logs()
    cfg = Config(config)
    typer.echo(f"NotiDeck Console: http://{host}:{port}")
    typer.echo(f"First-run token file (private): {cfg.token_path}")
    process = None
    if embedded_worker:
        if not cfg.database_url:
            raise typer.BadParameter("Complete setup, then restart with --embedded-worker")
        process = multiprocessing.get_context("spawn").Process(target=embedded, args=(str(cfg.directory),))
        process.start()
    try:
        uvicorn.run(create_app(cfg), host=host, port=port, access_log=False, proxy_headers=False)
    finally:
        if process:
            process.terminate()
            process.join(timeout=40)
            if process.is_alive():
                process.kill()


@app.command()
def worker(concurrency: int = typer.Option(1, min=1, max=32), config: Path | None = None):
    """Run a separately supervised delivery worker."""
    from notideck.worker import run

    logs()
    run(Config(config), concurrency)


@app.command()
def doctor(config: Path | None = None):
    cfg = Config(config)
    typer.echo(f"NotiDeck {__version__}; configuration directory: {cfg.directory}")
    if not cfg.database_url:
        typer.echo("Setup required. Start notideck serve and open Console.")
        raise typer.Exit(1)
    try:
        engine = engine_for(cfg.database_url)
        current = schema_current(engine)
        typer.echo(f"Database: {engine.dialect.name}; schema current: {current}")
        engine.dispose()
        if not current:
            raise typer.Exit(1)
    except Exception:
        typer.echo("Database unavailable or migration needed. Verify configuration and driver installation.")
        raise typer.Exit(1) from None


@db_app.command("status")
def db_status(config: Path | None = None):
    doctor(config)


@db_app.command("migrate")
def db_migrate(config: Path | None = None):
    cfg = Config(config)
    if not cfg.database_url:
        raise typer.BadParameter("Configure database through setup or NOTIDECK_DATABASE_URL first")
    engine = engine_for(cfg.database_url)
    migrate(engine)
    engine.dispose()
    typer.echo("Database migrated. Keep a verified backup before upgrades.")


@app.command("init")
def unattended(file: Path, config: Path | None = None):
    """Initialize from a private setup JSON file (same schema as POST /api/v1/setup)."""
    from fastapi.testclient import TestClient
    from notideck.api import create_app

    cfg = Config(config)
    if os.name != "nt" and file.stat().st_mode & 0o077:
        raise typer.BadParameter("Setup file must have mode 0600")
    with TestClient(create_app(cfg)) as client:
        result = client.post(
            "/api/v1/setup",
            content=file.read_bytes(),
            headers={
                "Content-Type": "application/json",
                "X-Bootstrap-Token": cfg.token_path.read_text(encoding="utf-8").strip(),
            },
        )
    if result.status_code != 200:
        typer.echo(
            "Initialization failed; validate setup fields, database availability and existing installation state."
        )
        raise typer.Exit(1)
    typer.echo(
        "Initialization complete. Securely remove the setup file containing your administrator password."
    )
