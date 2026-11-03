import os
import sys
import socket
import subprocess
import re
import time
import atexit
import argparse
import uvicorn

_TUNNEL_PROC = None

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(0.2)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def start_tunnel_if_available(port=8000) -> str | None:
    """Spawns Cloudflare Tunnel to allow phones on DIFFERENT Wi-Fi / 4G / 5G to connect."""
    global _TUNNEL_PROC
    cf_path = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
    if not os.path.exists(cf_path):
        return None

    try:
        print(" 🌐 Launching secure public tunnel (Cloudflare)...", flush=True)
        cmd = [cf_path, "tunnel", "--url", f"http://127.0.0.1:{port}"]
        _TUNNEL_PROC = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        atexit.register(cleanup_tunnel)

        # Read stderr to extract the generated trycloudflare.com URL
        url = None
        start_time = time.time()
        while time.time() - start_time < 12:
            line = _TUNNEL_PROC.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue
            match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if match:
                url = match.group(0)
                break

        if url:
            os.environ["PUBLIC_URL"] = url
            return url
    except Exception as e:
        print(f" ⚠️ Could not start tunnel: {e}", flush=True)

    return None

def cleanup_tunnel():
    global _TUNNEL_PROC
    if _TUNNEL_PROC and _TUNNEL_PROC.poll() is None:
        try:
            _TUNNEL_PROC.terminate()
            _TUNNEL_PROC.wait(timeout=2)
        except Exception:
            _TUNNEL_PROC.kill()

def print_banner(lan_ip, public_url=None, port=8000):
    active_mobile_url = public_url if public_url else f"http://{lan_ip}:{port}/"

    print("=" * 70)
    print(" 🚀 LineUp System - Smart Virtual Queue Management System")
    print("=" * 70)
    print(f" 📱 [Customer Mobile App]    : {active_mobile_url}")
    print(f" 💻 [Staff Dashboard]        : http://localhost:{port}/staff")
    print(f" 👑 [Admin Panel]            : http://localhost:{port}/admin")
    print(f" 🔑 [Login Portal]           : http://localhost:{port}/login")
    print(f" 📺 [Public TV Display Board]: http://localhost:{port}/tv")
    print(f" 🖨️  [QR Code Kiosk]          : http://localhost:{port}/kiosk")
    print(f" 📖 [Swagger API Docs]       : http://localhost:{port}/docs")
    print("-" * 70)

    if public_url:
        print(" 🌍 CROSS-NETWORK MODE ACTIVE (ដំណើរការលើគ្រប់ Wi-Fi & 4G/5G):")
        print(f"    Customers can scan QR Code from ANY Wi-Fi, 4G, or 5G mobile data!")
        print(f"    Public URL: {public_url}")
    else:
        print(" 🏠 LOCAL LAN WI-FI MODE (ភ្ជាប់ Wi-Fi តែមួយ):")
        print(f"    Mobile devices must connect to the same Wi-Fi router.")
        print(f"    Local URL: http://{lan_ip}:{port}/")

    print("-" * 70)
    print(" 🔑 Demo Accounts:")
    print("    • Staff: username: staff1 | password: staff123 (Counter 1)")
    print("    • Admin: username: admin  | password: admin123")
    print("=" * 70, flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LineUp Queue System Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on (default 8000)")
    parser.add_argument("--local", action="store_true", help="Force local-only mode (disable public tunnel)")
    parser.add_argument("--public", action="store_true", help="Enable public internet tunnel for any Wi-Fi / 4G / 5G")
    parser.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload on code change (default True)")
    args = parser.parse_args()

    port = args.port
    lan_ip = get_lan_ip()
    public_url = None

    # Enable public tunnel if requested or if not explicitly disabled with --local
    if not args.local:
        public_url = start_tunnel_if_available(port)

    print_banner(lan_ip, public_url, port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=args.reload, reload_dirs=["app"])
