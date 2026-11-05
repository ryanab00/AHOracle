import tkinter as tk
from tkinter import filedialog, simpledialog
import threading
import queue
import time
from pathlib import Path
from datetime import datetime
import json

from ahoracle import parse, pipeline
from ahoracle.db import make_engine
from sqlalchemy.orm import Session

VERSION = "0.3.2"
BG        = "#1e1e2e"
BG_PANEL  = "#282a36"
BG_LOG    = "#11111b"
FG        = "#f8f8f2"
FG_DIM    = "#6272a4"
ACCENT    = "#8be9fd"
OK_GREEN  = "#50fa7b"
WARN_YEL  = "#f1fa8c"
ERR_RED   = "#ff5555"

APP_DIR     = Path.home() / ".ahoracle"
CONFIG_FILE = APP_DIR / "config.json"
DEFAULTS = {"sv_file": None, "db_url": "sqlite:///ahoracle.db", "poll_seconds": 2, "stable_seconds": 3}

def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try: cfg.update(json.loads(CONFIG_FILE.read_text()))
        except Exception: pass
    return cfg

def save_config(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

class WatcherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"AHOracle Watcher · v{VERSION}")
        self.root.geometry("900x600")
        self.root.configure(bg=BG)
        
        self.queue = queue.Queue()
        self.is_ingesting = False
        self.watch_thread = None
        
        self.cfg = load_config()
        self._build_ui()
        
        self.root.after(100, self._poll_queue)
        
        if self.cfg.get("sv_file"):
            self._start_watcher()

    def _build_ui(self):
        # 1. Header
        header = tk.Frame(self.root, bg=BG, padx=15, pady=10)
        header.pack(side="top", fill="x")
        tk.Label(header, text="AHOracle Watcher", font=("Segoe UI", 16, "bold"), bg=BG, fg=FG).pack(side="left")
        self.status_lbl = tk.Label(header, text="Idle", font=("Segoe UI", 10), bg=BG, fg=FG_DIM)
        self.status_lbl.pack(side="right")

        # 2. Info Panel
        panel = tk.Frame(self.root, bg=BG_PANEL, padx=15, pady=10)
        panel.pack(side="top", fill="x", padx=10)
        
        row1 = tk.Frame(panel, bg=BG_PANEL)
        row1.pack(fill="x", pady=5)
        tk.Label(row1, text="Save file", width=10, anchor="w", bg=BG_PANEL, fg=FG_DIM).pack(side="left")
        self.lbl_sv = tk.Label(row1, text=self.cfg.get("sv_file", "Not set"), bg=BG_PANEL, fg=FG)
        self.lbl_sv.pack(side="left", padx=10)
        tk.Button(row1, text="Change...", command=self._on_browse_sv, bg=BG_PANEL, fg=ACCENT, relief="flat").pack(side="right")

        row2 = tk.Frame(panel, bg=BG_PANEL)
        row2.pack(fill="x", pady=5)
        tk.Label(row2, text="Database", width=10, anchor="w", bg=BG_PANEL, fg=FG_DIM).pack(side="left")
        self.lbl_db = tk.Label(row2, text=self.cfg.get("db_url", "sqlite:///ahoracle.db"), bg=BG_PANEL, fg=FG)
        self.lbl_db.pack(side="left", padx=10)
        tk.Button(row2, text="Change...", command=self._on_change_db, bg=BG_PANEL, fg=ACCENT, relief="flat").pack(side="right")

        # 3. Buttons (Pack at BOTTOM before the log area!)
        btn_frame = tk.Frame(self.root, bg=BG, padx=15, pady=15)
        btn_frame.pack(side="bottom", fill="x")
        
        self.btn_ingest = tk.Button(btn_frame, text="Ingest now", command=self._on_ingest_now, bg=BG_PANEL, fg=FG, relief="flat", width=15)
        self.btn_ingest.pack(side="left")
        tk.Button(btn_frame, text="Clear log", command=self._on_clear_log, bg=BG_PANEL, fg=FG, relief="flat", width=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Quit", command=self.root.quit, bg=BG_PANEL, fg=ERR_RED, relief="flat", width=15).pack(side="right")

        # 4. Log Area (Pack last, it will fill the middle space)
        log_frame = tk.Frame(self.root, bg=BG_PANEL, padx=15, pady=10)
        log_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        tk.Label(log_frame, text="ACTIVITY LOG", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x")
        
        self.log_text = tk.Text(log_frame, bg=BG_LOG, fg=FG, font=("Consolas", 10), relief="flat", wrap="word")
        self.log_text.pack(fill="both", expand=True, pady=5)
        self.log_text.tag_config("error", foreground=ERR_RED)
        self.log_text.tag_config("success", foreground=OK_GREEN)
        self.log_text.tag_config("info", foreground=ACCENT)

    def _append_log(self, msg: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"{ts}  {msg}\n", tag)
        self.log_text.see("end")

    def _set_status(self, text: str, color: str):
        self.status_lbl.config(text=text, fg=color)

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "log": self._append_log(data)
                elif msg_type == "log_err": self._append_log(data, "error")
                elif msg_type == "log_ok": self._append_log(data, "success")
                elif msg_type == "status": self._set_status(data[0], data[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _on_browse_sv(self):
        path = filedialog.askopenfilename(title="Select SavedVariables file", filetypes=[("Lua files", "*.lua")])
        if path:
            self.cfg["sv_file"] = path
            save_config(self.cfg)
            self.lbl_sv.config(text=path)
            self._start_watcher()

    def _on_change_db(self):
        url = simpledialog.askstring("Database URL", "Enter Database URL:", initialvalue=self.cfg.get("db_url", ""))
        if url:
            self.cfg["db_url"] = url
            save_config(self.cfg)
            self.lbl_db.config(text=url)

    def _on_ingest_now(self):
        if self.is_ingesting:
            self.queue.put(("log_err", "Ingest already in progress."))
            return
        if not self.cfg.get("sv_file"):
            self.queue.put(("log_err", "No save file selected."))
            return
            
        self.is_ingesting = True
        self.btn_ingest.config(state="disabled")
        self.queue.put(("log", "Manual ingest requested."))
        threading.Thread(target=self._ingest_once, args=(Path(self.cfg["sv_file"]), self.cfg.get("db_url", "sqlite:///ahoracle.db")), daemon=True).start()

    def _start_watcher(self):
        if self.watch_thread and self.watch_thread.is_alive(): return
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()

    def _watch_loop(self):
        sv_path = Path(self.cfg["sv_file"])
        if not sv_path.exists():
            self.queue.put(("status", ("File not found", ERR_RED)))
            return
            
        self.queue.put(("status", ("Watching", OK_GREEN)))
        self.queue.put(("log", f"Watching {sv_path.name}"))
        
        last_mtime = sv_path.stat().st_mtime
        pending_since = None
        
        while True:
            try:
                mtime = sv_path.stat().st_mtime
                if mtime != last_mtime:
                    pending_since = time.time()
                    last_mtime = mtime
                elif pending_since and time.time() - pending_since > 3:
                    if not self.is_ingesting:
                        self.queue.put(("log", "File change detected. Starting auto-ingest..."))
                        self.is_ingesting = True
                        self._ingest_once(sv_path, self.cfg.get("db_url", "sqlite:///ahoracle.db"))
                    pending_since = None
            except Exception:
                pass
            time.sleep(2)

    def _ingest_once(self, sv_path: Path, db_url: str):
        self.queue.put(("status", ("Ingesting...", WARN_YEL)))
        try:
            self.queue.put(("log", "Parsing SavedVariables..."))
            db = parse.parse_saved_variables(sv_path)
            
            self.queue.put(("log", "Connecting to database..."))
            engine = make_engine(db_url)
            
            with Session(engine) as session:
                for item in parse.extract_scans(db):
                    # The parser might yield a tuple (faction, scan_dict) or just scan_dict
                    if isinstance(item, tuple):
                        faction, scan = item
                    else:
                        scan = item
                        faction = scan.get('faction', 'Unknown')

                    self.queue.put(("log", f"Uploading {faction} to cloud..."))
                    
                    # Ensure the pipeline gets the dictionary
                    r = pipeline.ingest_scan(session, scan)
                    
                    if r.get("skipped"):
                        self.queue.put(("log", f"{faction}: Skipped (already exists)"))
                    else:
                        self.queue.put(("log_ok", f"{faction}: {r['listings']} listings | {r['vanished']} vanished"))
            
            self.queue.put(("status", ("Watching", OK_GREEN)))
            self.queue.put(("log_ok", "✅ Ingest complete."))
            
        except Exception as e:
            self.queue.put(("status", ("Error", ERR_RED)))
            self.queue.put(("log_err", f"Ingest failed: {e}"))
        finally:
            self.is_ingesting = False
            self.root.after(0, lambda: self.btn_ingest.config(state="normal"))

    def _on_clear_log(self):
        self.log_text.delete("1.0", "end")

if __name__ == "__main__":
    root = tk.Tk()
    app = WatcherApp(root)
    root.mainloop()