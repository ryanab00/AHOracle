import os
import subprocess
import sys
import time


def run_dev():
    print("Starting AH Oracle dev stack...")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")

    processes = []

    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0

    try:
        # 1. Watcher GUI (Tkinter)
        print("Starting watcher...")
        watcher_proc = subprocess.Popen(
            [sys.executable, "watcher_gui.py"],
            cwd=backend_dir,
            creationflags=CREATE_NEW_CONSOLE,
        )
        processes.append(watcher_proc)

        # 2. FastAPI
        # NOTE: uvicorn's --reload spawn child needs `backend/` on sys.path.
        # That's provided by .venv/Lib/site-packages/ahoracle.pth — do not
        # remove it without also restoring a PYTHONPATH workaround.
        print("Starting API...")
        api_proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "ahoracle.api.main:app",
                "--reload",
                "--port", "8000",
            ],
            cwd=backend_dir,
            creationflags=CREATE_NEW_CONSOLE,
        )
        processes.append(api_proc)

        # 3. Nuxt frontend
        print("Starting frontend...")
        frontend_proc = subprocess.Popen(
            "npm run dev",
            cwd=frontend_dir,
            shell=True,
            creationflags=CREATE_NEW_CONSOLE,
        )
        processes.append(frontend_proc)

        print()
        print("All services started:")
        print("  Frontend: http://localhost:3000")
        print("  API:      http://localhost:8000/docs")
        print()
        print("Ctrl+C here to stop everything.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        for p in processes:
            if sys.platform == "win32":
                subprocess.call(
                    ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                p.terminate()
        print("Done.")


if __name__ == "__main__":
    run_dev()