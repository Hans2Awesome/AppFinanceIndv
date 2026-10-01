#!/usr/bin/env python3
"""
Automated 1-Click Runner for Finance App.
Starts:
1. FastAPI Backend (port 8000)
2. Cloudflare Tunnel for Backend (updates mobile/services/api.ts automatically)
3. Cloudflare Tunnel for Expo Metro (port 8081)
4. Expo Metro Bundler (port 8081)
5. Generates QR Code for Expo Go in terminal & browser link
"""

import os
import re
import sys
import time
import signal
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
MOBILE_DIR = ROOT_DIR / "mobile"
API_TS_FILE = MOBILE_DIR / "services" / "api.ts"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
VENV_UVICORN = BACKEND_DIR / ".venv" / "bin" / "uvicorn"

processes = []

def cleanup(sig=None, frame=None):
    print("\n[INFO] Menghentikan semua layanan...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    # Kill any leftover orphaned processes on ports 8000 and 8081
    subprocess.run("pkill -f 'uvicorn.*8000' || true", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -f 'cloudflared tunnel' || true", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -f 'expo start' || true", shell=True, stderr=subprocess.DEVNULL)
    print("[INFO] Semua layanan berhasil dihentikan.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def kill_existing():
    subprocess.run("pkill -f 'uvicorn.*8000' || true", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -f 'cloudflared tunnel' || true", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -f 'expo start' || true", shell=True, stderr=subprocess.DEVNULL)
    time.sleep(1)

def extract_tunnel_url(log_file, timeout=20):
    start = time.time()
    url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
    while time.time() - start < timeout:
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                matches = url_pattern.findall(content)
                if matches:
                    return matches[0]
        time.sleep(0.5)
    return None

def update_mobile_api_url(new_url):
    if not API_TS_FILE.exists():
        print(f"[WARN] File {API_TS_FILE} tidak ditemukan.")
        return
    text = API_TS_FILE.read_text(encoding='utf-8')
    pattern = r"return 'https://[a-zA-Z0-9-]+\.trycloudflare\.com';"
    replacement = f"return '{new_url}';"
    if re.search(pattern, text):
        new_text = re.sub(pattern, replacement, text)
    else:
        # Fallback replacement in getBaseUrl
        new_text = re.sub(
            r"const getBaseUrl = \(\) => \{\s*return '[^']+';",
            f"const getBaseUrl = () => {{\n  return '{new_url}';",
            text
        )
    API_TS_FILE.write_text(new_text, encoding='utf-8')
    print(f"[OK] Backend URL di mobile/services/api.ts diperbarui -> {new_url}")

def main():
    print("=" * 65)
    print("   MEMULAI PERSONAL FINANCE APP (BACKEND + MOBILE EXPO)")
    print("=" * 65)

    print("[1/5] Membersihkan proses lama...")
    kill_existing()

    os.makedirs("/tmp/finance_logs", exist_ok=True)
    backend_log = "/tmp/finance_logs/backend.log"
    backend_tunnel_log = "/tmp/finance_logs/backend_tunnel.log"
    metro_tunnel_log = "/tmp/finance_logs/metro_tunnel.log"
    metro_log = "/tmp/finance_logs/metro.log"

    for f in [backend_log, backend_tunnel_log, metro_tunnel_log, metro_log]:
        if os.path.exists(f):
            os.remove(f)

    # 1. Jalankan Backend
    print("[2/5] Menjalankan Backend FastAPI (Port 8000)...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)
    p_backend = subprocess.Popen(
        f"{VENV_UVICORN} backend.app.main:app --host 0.0.0.0 --port 8000",
        cwd=str(ROOT_DIR),
        shell=True,
        stdout=open(backend_log, 'w'),
        stderr=subprocess.STDOUT,
        env=env
    )
    processes.append(p_backend)

    # 2. Jalankan Cloudflare Tunnel Backend
    print("[3/5] Mengaktifkan Cloudflare Tunnel untuk Backend...")
    p_btunnel = subprocess.Popen(
        f"cloudflared tunnel --edge-ip-version 4 --protocol http2 --url http://localhost:8000 > {backend_tunnel_log} 2>&1",
        shell=True
    )
    processes.append(p_btunnel)

    backend_url = extract_tunnel_url(backend_tunnel_log)
    if not backend_url:
        print("[ERROR] Gagal mendapatkan URL Cloudflare untuk Backend.")
        cleanup()
    print(f"[OK] Backend Online: {backend_url}")
    update_mobile_api_url(backend_url)

    # 3. Jalankan Cloudflare Tunnel untuk Metro Bundler
    print("[4/5] Mengaktifkan Cloudflare Tunnel untuk Expo Metro...")
    p_mtunnel = subprocess.Popen(
        f"cloudflared tunnel --edge-ip-version 4 --protocol http2 --url http://localhost:8081 > {metro_tunnel_log} 2>&1",
        shell=True
    )
    processes.append(p_mtunnel)

    metro_tunnel_url = extract_tunnel_url(metro_tunnel_log)
    if not metro_tunnel_url:
        print("[ERROR] Gagal mendapatkan URL Cloudflare untuk Metro.")
        cleanup()

    domain = metro_tunnel_url.replace("https://", "").replace("http://", "")
    expo_url = f"exp://{domain}"

    # 4. Jalankan Expo Metro Bundler
    print("[5/5] Menjalankan Expo Metro Bundler (Port 8081)...")
    p_metro = subprocess.Popen(
        "npx expo start --port 8081",
        cwd=str(MOBILE_DIR),
        shell=True,
        stdout=open(metro_log, 'w'),
        stderr=subprocess.STDOUT
    )
    processes.append(p_metro)

    time.sleep(2)

    # 5. Tampilkan QR Code & Info
    print("\n" + "=" * 65)
    print("   APLIKASI SIAP DIJALANKAN DI EXPO GO!")
    print("=" * 65)
    print(f"Backend API URL : {backend_url}")
    print(f"Expo Go URL     : {expo_url}")
    print(f"Web QR Image    : https://api.qrserver.com/v1/create-qr-code/?size=350x350&data={expo_url}")
    print("=" * 65)

    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=2)
        qr.add_data(expo_url)
        print("\nScan QR Code di bawah dengan Expo Go di HP Anda:\n")
        qr.print_ascii(invert=True)
    except Exception:
        pass

    print("\n[INFO] Tekan Ctrl+C di terminal ini kapan saja untuk menghentikan server.\n")

    # Monitor proses
    while True:
        time.sleep(1)
        if p_backend.poll() is not None:
            print("[WARN] Backend berhenti secara tidak terduga.")
            break
        if p_metro.poll() is not None:
            print("[WARN] Expo Metro berhenti secara tidak terduga.")
            break

if __name__ == "__main__":
    main()
