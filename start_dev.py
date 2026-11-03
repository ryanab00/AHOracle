import subprocess
import sys
import time
import os

def run_dev():
    print("🚀 Starting AH Oracle Local Development Environment...")
    
    # Define paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend") 
    frontend_dir = os.path.join(root_dir, "frontend")

    processes = []

    # Windows-specific flag to open a new terminal window for each process
    # If not on Windows, this defaults to 0 (no special flags)
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0

    try:
        # 1. Start ETL Watcher GUI (Python)
        print("📡 Starting ETL Watcher GUI...")
        watcher_cmd = [sys.executable, "watcher_gui.py"]
        watcher_proc = subprocess.Popen(
            watcher_cmd, 
            cwd=backend_dir, 
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(watcher_proc)

        # 2. Start FastAPI (Python)
        print("⚙️  Starting FastAPI Backend...")
        api_cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"]
        api_proc = subprocess.Popen(
            api_cmd, 
            cwd=backend_dir, 
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(api_proc)

        # 3. Start Nuxt Frontend (Node)
        print("🖥️  Starting Nuxt Frontend...")
        # shell=True is required for npm on Windows
        frontend_proc = subprocess.Popen(
            "npm run dev", 
            cwd=frontend_dir, 
            shell=True,
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(frontend_proc)

        print("\n✅ All services launched in separate windows!")
        print("🌐 Frontend: http://localhost:3000")
        print("🔌 API:      http://localhost:8000/docs")
        print("🛑 Press Ctrl+C here to stop everything.\n")

        # Keep the main script alive so Ctrl+C works
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down all services...")
        for p in processes:
            if sys.platform == "win32":
                # Windows requires killing the process tree to stop npm/uvicorn cleanly
                subprocess.call(
                    ['taskkill', '/F', '/T', '/PID', str(p.pid)], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
            else:
                p.terminate()
        print("👋 Goodbye!")

if __name__ == "__main__":
    run_dev()