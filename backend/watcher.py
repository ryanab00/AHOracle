
#!/usr/bin/env python3
"""AHOracle Watcher — auto-ingest SavedVariables on change.

For a graphical version, use watcher_gui.py instead.

Usage:
    python watcher.py                   # auto-detects WoW, runs forever
    python watcher.py --once            # ingest once and exit
    python watcher.py --sv-file PATH    # explicit save file
    python watcher.py --db URL          # explicit database
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend import parse, pipeline
from backend.db import make_engine, ensure_views
from backend.models import Base



from backend.ahoracle.config import (
    load as load_config, save as save_config,
    find_sv_file, is_valid_sv_file,
)


# ─── Rich output (falls back to plain if rich isn't installed) ───────────

try:
    from rich.console import Console
    from rich.text import Text
    _console = Console()

    def _emit(markup: str) -> None:
        _console.print(markup, highlight=False)
except ImportError:
    import re
    _ansi_strip = re.compile(r"\[/?[a-zA-Z0-9_ #]+\]")

    def _emit(markup: str) -> None:
        print(_ansi_strip.sub("", markup))


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    _emit(f"[dim]{_ts()}[/dim]  {msg}")


# ─── Ingest ──────────────────────────────────────────────────────────────

def ingest_once(sv_path: Path, db_url: str) -> None:
    _log(f"Reading [cyan]{sv_path.name}[/cyan]")
    try:
        db = parse.parse_saved_variables(sv_path)
    except Exception as e:
        _log(f"[red]Parse error:[/red] {e}")
        return

    try:
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        ensure_views(engine)
    except Exception as e:
        _log(f"[red]DB error:[/red] {e}")
        return

    try:
        results = []
        with Session(engine) as session:
            for faction, scan in parse.extract_scans(db):
                r = pipeline.ingest_scan(session, scan)
                results.append(r)
            session.commit()
    except Exception as e:
        _log(f"[red]Ingest error:[/red] {e}")
        return

    if not results:
        _log("[yellow](no populated faction slots)[/yellow]")
        return

    for r in results:
        if r.get("skipped"):
            _log(f"  {r['faction']:9s} [dim]skipped ({r['skipped']})[/dim]")
        else:
            v = r["vanished"]
            v_style = "green" if v else "dim"
            _log(
                f"  {r['faction']:9s} "
                f"[cyan]{r['listing_count']:>6d}[/cyan] listings  "
                f"[{v_style}]{v:>5d} vanished[/{v_style}]  "
                f"[dim]{r['zone']}[/dim]"
            )


# ─── Watch loop ──────────────────────────────────────────────────────────

def watch(sv_path: Path, db_url: str, poll: int, stable: int) -> None:
    _log(f"Watching [cyan]{sv_path}[/cyan]")
    _log(f"Database [cyan]{db_url}[/cyan]")
    _log("[dim]Ctrl+C to stop.[/dim]")
    print()

    ingest_once(sv_path, db_url)

    last_mtime    = sv_path.stat().st_mtime
    pending_since = None

    try:
        while True:
            time.sleep(poll)
            try:
                mtime = sv_path.stat().st_mtime
            except FileNotFoundError:
                continue

            if mtime != last_mtime:
                pending_since = time.time()
                last_mtime    = mtime
                continue

            if pending_since is not None and (time.time() - pending_since) >= stable:
                print()
                _log("[cyan]── File changed — ingesting ──[/cyan]")
                ingest_once(sv_path, db_url)
                pending_since = None
    except KeyboardInterrupt:
        _log("Stopped.")


# ─── Entry point ─────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="AHOracle Watcher")
    ap.add_argument("--sv-file", type=Path, help="Path to AHOracle.lua")
    ap.add_argument("--db",      help="SQLAlchemy DB URL")
    ap.add_argument("--once",    action="store_true", help="Ingest once and exit")
    args = ap.parse_args()

    cfg = load_config()

    # Resolve SV file
    sv_path = args.sv_file or (Path(cfg["sv_file"]) if cfg.get("sv_file") else None)
    if not sv_path or not sv_path.exists():
        _log("Looking for WoW installation...")
        detected = find_sv_file()
        if detected:
            _log(f"Auto-detected: [cyan]{detected}[/cyan]")
            sv_path = detected
            cfg["sv_file"] = str(detected)
            save_config(cfg)
        else:
            _log("[red]Could not locate AHOracle.lua automatically.[/red]")
            _log("Run [cyan]python watcher_gui.py[/cyan] for a setup window,")
            _log("or pass [cyan]--sv-file[/cyan] with the full path.")
            return 1

    db_url = args.db or cfg["db_url"]

    if args.once:
        ingest_once(sv_path, db_url)
        return 0

    watch(sv_path, db_url,
          poll=int(cfg["poll_seconds"]),
          stable=int(cfg["stable_seconds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())