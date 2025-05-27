import os
import subprocess
from app import create_app, socketio

app = create_app()

def is_wsl_environment():
    """Detects if the app is running in a WSL environment"""
    try:
        with open("/proc/sys/kernel/osrelease", "r") as f:
            osrelease = f.read().lower()
            return "microsoft" in osrelease or "wsl" in osrelease
    except Exception:
        return False

def start_novnc_service():
    """Starts the noVNC systemd service if it's not already running"""
    try:
        # Check if service is active
        status = subprocess.run(
            ["systemctl", "is-active", "--quiet", "novnc.service"]
        )
        if status.returncode != 0:
            print("ℹ️  Starting noVNC service via systemd...")
            subprocess.run(["sudo", "systemctl", "start", "novnc.service"])
        else:
            print("✅ noVNC service already running")
    except Exception as e:
        print(f"❌ Failed to check/start noVNC service: {e}")

if __name__ == '__main__':
    if not is_wsl_environment():
        print("🖥️  Native Linux detected. Ensuring noVNC service is running...")
        start_novnc_service()
    else:
        print("💡 WSL environment detected. Skipping noVNC systemd service startup.")

    socketio.run(app, debug=False, host='0.0.0.0')
