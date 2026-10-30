import subprocess
import sys
import time
import os
import signal

def run_dev():
    print("🚀 Starting AH Oracle Local Development Environment...")
    
    # Define paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    etl_dir = os.path.join(root_dir, "ahoracle-etl")
    frontend_dir = os.path.join(root_dir, "frontend")
    
    # Update this path if your WoW installation is somewhere else
    # By default, we point the watcher directly at AHDB's file
    wow_path = r"C:\Program Files (x86)\World of Warcraft\_classic_era_\WTF\Account\333716566#1\SavedVariables\AuctionDB.lua"

    processes = []

    try:
        # 1. Start ETL Watcher (Python)
        print("📡 Starting ETL Watcher...")
        watcher_cmd = [sys.executable, "watcher.py", "--sv-file", wow_path, "--once"]
        # Note: You can remove "--once" if you want it to run continuously
        watcher_proc = subprocess.Popen(watcher_cmd, cwd=etl_dir)
        processes.append(watcher_proc)

        # 2. Start FastAPI (Python)
        print("⚙️  Starting FastAPI Backend...")
        api_cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"]
        api_proc = subprocess.Popen(api_cmd, cwd=etl_dir)
        processes.append(api_proc)

        # 3. Start Nuxt Frontend (Node)
        print("🖥️  Starting Nuxt Frontend...")
        # shell=True is required for npm on Windows
        frontend_proc = subprocess.Popen("npm run dev", cwd=frontend_dir, shell=True)
        processes.append(frontend_proc)

        print("\n✅ All services are running!")
        print("🌐 Frontend: http://localhost:3000")
        print("🔌 API:      http://localhost:8000/docs")
        print("🛑 Press Ctrl+C to stop everything.\n")

        # Keep the main script alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        for p in processes:
            if sys.platform == "win32":
                # Windows requires killing the process tree to stop npm/uvicorn cleanly
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                p.terminate()
        print("👋 Goodbye!")

if __name__ == "__main__":
    run_dev()