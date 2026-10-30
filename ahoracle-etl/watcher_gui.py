#!/usr/bin/env python3
"""AHOracle Watcher — graphical interface.

A dark-themed Tkinter window that:
  - Auto-detects your WoW install on first run
  - Lets you point at any AHOracle.lua manually
  - Watches the file and ingests on every change (WoW logout / reload)
  - Shows a live activity log
  - Persists everything to ~/.ahoracle/config.json
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from sqlalchemy.orm import Session

from ahoracle_etl import parse, pipeline
from ahoracle_etl.db import make_engine, ensure_views
from ahoracle_etl.models import Base

from config import (
    APP_DIR, CONFIG_FILE,
    load as load_config, save as save_config,
    find_sv_file, is_valid_sv_file, SV_FILENAME,
)


VERSION = "0.3.0"


# ─── Palette ─────────────────────────────────────────────────────────────

BG        = "#1e1e2e"
BG_PANEL  = "#282a36"
BG_LOG    = "#11111b"
FG        = "#f8f8f2"
FG_DIM    = "#6272a4"
ACCENT    = "#8be9fd"
OK_GREEN  = "#50fa7b"
WARN_YEL  = "#f1fa8c"
ERR_RED   = "#ff5555"
PURPLE    = "#bd93f9"


class WatcherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg  = load_config()
        self.msg_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.watcher_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.ingest_lock = threading.Lock()
        self.running = False

        self._build_ui()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self._ensure_ready()

    # ─── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        self.root.title(f"AHOracle Watcher  ·  v{VERSION}")
        self.root.geometry("820x600")
        self.root.minsize(680, 460)
        self.root.configure(bg=BG)

        # Header ---------------------------------------------------------
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(
            header, text="AHOracle Watcher",
            bg=BG, fg=FG, font=("Segoe UI", 16, "bold"),
        ).pack(side="left")

        self.status_dot = tk.Label(
            header, text="●", bg=BG, fg=WARN_YEL, font=("Segoe UI", 16),
        )
        self.status_dot.pack(side="right", padx=(4, 0))

        self.status_label = tk.Label(
            header, text="Starting…",
            bg=BG, fg=FG_DIM, font=("Segoe UI", 10),
        )
        self.status_label.pack(side="right")

        # Info panel -----------------------------------------------------
        panel = tk.Frame(self.root, bg=BG_PANEL, padx=12, pady=10)
        panel.pack(fill="x", padx=16, pady=(0, 8))

        self._add_info_row(panel, "Save file", self._on_browse_sv, "sv_value")
        self._add_info_row(panel, "Database",  self._on_change_db, "db_value")

        # Log panel ------------------------------------------------------
        log_frame = tk.Frame(self.root, bg=BG_PANEL, padx=12, pady=8)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(
            log_frame, text="ACTIVITY LOG",
            bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.log = tk.Text(
            log_frame, bg=BG_LOG, fg=FG,
            insertbackground=FG,
            font=("Consolas", 9),
            wrap="word", relief="flat",
            padx=10, pady=8,
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)

        for name, colour in (
            ("info", FG), ("dim", FG_DIM), ("ok", OK_GREEN),
            ("warn", WARN_YEL), ("error", ERR_RED),
            ("accent", ACCENT), ("ts", FG_DIM),
        ):
            self.log.tag_configure(name, foreground=colour)

        # Button bar -----------------------------------------------------
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=16, pady=(0, 14))

        self._button(bar, "Ingest now",   self._on_ingest_now)
        self._button(bar, "Open folder",  self._on_open_folder)
        self._button(bar, "Clear log",    self._on_clear_log)
        self._button(bar, "Quit",         self._on_quit, side="right")

    def _add_info_row(self, parent, label, cb, attr_name):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=3)

        tk.Label(
            row, text=label, bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 9, "bold"), width=10, anchor="w",
        ).pack(side="left")

        value = tk.Label(
            row, text="—", bg=BG_PANEL, fg=FG,
            font=("Consolas", 8), anchor="w", justify="left",
        )
        value.pack(side="left", fill="x", expand=True, padx=(0, 8))
        setattr(self, attr_name, value)

        tk.Button(
            row, text="Change…",
            bg=BG_PANEL, fg=ACCENT,
            activebackground=BG_PANEL, activeforeground=FG,
            relief="flat", bd=0, font=("Segoe UI", 8),
            cursor="hand2", command=cb,
        ).pack(side="right")

    def _button(self, parent, text, cmd, side="left"):
        b = tk.Button(
            parent, text=text, command=cmd,
            bg=BG_PANEL, fg=FG,
            activebackground=ACCENT, activeforeground=BG,
            relief="flat", bd=0, padx=14, pady=6,
            font=("Segoe UI", 9), cursor="hand2",
        )
        b.pack(side=side, padx=(0, 6))
        return b

    # ─── Log helpers ────────────────────────────────────────────────────

    def _append_log(self, msg: str, tag: str = "info"):
        self.log.configure(state="normal")
        self.log.insert("end", datetime.now().strftime("%H:%M:%S") + "  ", "ts")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, text: str, colour: str):
        self.status_label.configure(text=text, fg=colour)
        self.status_dot.configure(fg=colour)

    def _set_status_safe(self, text: str, colour: str):
        self.msg_queue.put(("__status__", (text, colour)))

    # ─── First-run / watcher bootstrap ─────────────────────────────────

    def _ensure_ready(self):
        if not self.cfg.get("sv_file") or not Path(self.cfg["sv_file"]).exists():
            self._append_log("Looking for WoW install…", "dim")
            detected = find_sv_file()
            if detected:
                self.cfg["sv_file"] = str(detected)
                save_config(self.cfg)
                self._append_log(f"Auto-detected: {detected}", "ok")
            else:
                self._append_log(
                    "Could not auto-detect WoW — click 'Change…' next to Save file.",
                    "warn",
                )
                self.root.after(200, self._prompt_for_sv_file)

        self._refresh_info()
        self._start_watcher()

    def _refresh_info(self):
        self.sv_value.configure(text=self.cfg.get("sv_file") or "—")
        self.db_value.configure(text=self.cfg.get("db_url") or "—")

    def _start_watcher(self):
        if self.running:
            return
        sv = self.cfg.get("sv_file")
        if not sv or not Path(sv).exists():
            self._set_status("No save file", ERR_RED)
            return
        self.stop_event.clear()
        self.watcher_thread = threading.Thread(
            target=self._watch_loop, daemon=True,
        )
        self.watcher_thread.start()
        self.running = True
        self._set_status("Watching", OK_GREEN)

    def _restart_watcher(self):
        self.stop_event.set()
        if self.watcher_thread:
            self.watcher_thread.join(timeout=2)
        self.running = False
        self._start_watcher()

    # ─── Watcher thread ────────────────────────────────────────────────

    def _watch_loop(self):
        sv_path = Path(self.cfg["sv_file"])
        db_url  = self.cfg["db_url"]
        poll    = int(self.cfg.get("poll_seconds") or 2)
        stable  = int(self.cfg.get("stable_seconds") or 3)

        self.msg_queue.put(("dim", f"Watching  {sv_path}"))
        self.msg_queue.put(("dim", f"Database  {db_url}"))

        self._ingest_once(sv_path, db_url)

        try:
            last_mtime = sv_path.stat().st_mtime
        except FileNotFoundError:
            self.msg_queue.put(("error", "Save file disappeared."))
            self._set_status_safe("File missing", ERR_RED)
            return

        pending_since = None

        while not self.stop_event.is_set():
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
                self.msg_queue.put(("accent", "── File changed — ingesting ──"))
                self._set_status_safe("Ingesting…", WARN_YEL)
                self._ingest_once(sv_path, db_url)
                self._set_status_safe("Watching", OK_GREEN)
                pending_since = None

    def _ingest_once(self, sv_path: Path, db_url: str):
        if not self.ingest_lock.acquire(blocking=False):
            # Another ingest is already running
            self.msg_queue.put(("dim", "(ingest already in progress — skipping)"))
            return
        try:
            try:
                db = parse.parse_saved_variables(sv_path)
            except Exception as e:
                self.msg_queue.put(("error", f"Parse error: {e}"))
                self._set_status_safe("Parse error", ERR_RED)
                return

            try:
                engine = make_engine(db_url)
                Base.metadata.create_all(engine)
                ensure_views(engine)
            except Exception as e:
                self.msg_queue.put(("error", f"DB error: {e}"))
                self._set_status_safe("DB error", ERR_RED)
                return

            try:
                results = []
                with Session(engine) as session:
                    for faction, scan in parse.extract_scans(db):
                        r = pipeline.ingest_scan(session, scan)
                        results.append(r)
                    session.commit()
            except Exception as e:
                self.msg_queue.put(("error", f"Ingest error: {e}"))
                self._set_status_safe("Ingest error", ERR_RED)
                return

            if not results:
                self.msg_queue.put(("dim", "(no populated faction slots)"))
                return

            for r in results:
                if r.get("skipped"):
                    self.msg_queue.put(
                        ("dim", f"  {r['faction']:9s}  skipped ({r['skipped']})")
                    )
                else:
                    v = r["vanished"]
                    self.msg_queue.put((
                        "info",
                        f"  {r['faction']:9s}  {r['listing_count']:>6d} listings"
                        f"  |  {v:>5d} vanished  |  {r['zone']}"
                    ))
                    if v:
                        self.msg_queue.put((
                            "ok", f"       ↳ {v} vanish events recorded"
                        ))
        finally:
            self.ingest_lock.release()

    # ─── Queue pump (main thread) ──────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                tag, payload = self.msg_queue.get_nowait()
                if tag == "__status__":
                    text, colour = payload  # type: ignore[misc]
                    self._set_status(text, colour)
                else:
                    self._append_log(payload, tag)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    # ─── Button handlers ───────────────────────────────────────────────

    def _on_browse_sv(self):
        self._prompt_for_sv_file()

    def _prompt_for_sv_file(self):
        current = self.cfg.get("sv_file") or str(Path.home())
        p = Path(current)
        initial = str(p.parent if p.is_file() else p)

        path = filedialog.askopenfilename(
            title="Locate AHOracle.lua",
            initialdir=initial,
            filetypes=[
                ("AHOracle SavedVariables", SV_FILENAME),
                ("Lua files", "*.lua"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        p = Path(path)
        if not is_valid_sv_file(p):
            if not messagebox.askyesno(
                "Wrong file?",
                f"{p.name} doesn't match {SV_FILENAME}.\n\nUse it anyway?",
            ):
                return

        self.cfg["sv_file"] = str(p)
        save_config(self.cfg)
        self._refresh_info()
        self._append_log(f"Save file set to {p}", "ok")
        self._restart_watcher()

    def _on_change_db(self):
        current = self.cfg.get("db_url") or "sqlite:///ahoracle.db"
        new = simpledialog.askstring(
            "Database URL",
            "SQLAlchemy connection URL.\n"
            "Leave blank to use local SQLite.\n\n"
            "Examples:\n"
            "  sqlite:///ahoracle.db\n"
            "  postgresql+psycopg://user:pass@host/db",
            initialvalue=current,
            parent=self.root,
        )
        if new is None:
            return
        self.cfg["db_url"] = new.strip() or "sqlite:///ahoracle.db"
        save_config(self.cfg)
        self._refresh_info()
        self._append_log(f"Database set to {self.cfg['db_url']}", "ok")
        self._restart_watcher()

    def _on_ingest_now(self):
        sv = self.cfg.get("sv_file")
        if not sv or not Path(sv).exists():
            self._append_log("No save file configured.", "error")
            return
        self._append_log("Manual ingest requested.", "accent")
        threading.Thread(
            target=lambda: self._ingest_once(Path(sv), self.cfg["db_url"]),
            daemon=True,
        ).start()

    def _on_open_folder(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(APP_DIR))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(APP_DIR)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(APP_DIR)])
        except Exception as e:
            self._append_log(f"Could not open folder: {e}", "error")

    def _on_clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _on_quit(self):
        self.stop_event.set()
        self.root.after(200, self.root.destroy)


def main() -> int:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    WatcherApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())