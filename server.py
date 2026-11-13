#!/usr/bin/env python3
"""
Local-First Phone Recovery & GPS Tracking Server
================================================
Zero-cloud, privacy-focused tracking dashboard and backend.
All location data, battery status, device metadata, and pre-shutdown
snapshots stay strictly in your local SQLite database on your laptop.
"""

import sys
import os
import json
import sqlite3
import secrets
import hashlib
import time
import socket
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from contextlib import contextmanager

DB_PATH = os.environ.get("TRACKER_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.db"))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

@contextmanager
def get_db():
    global DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
    except sqlite3.OperationalError:
        fallback_dir = os.path.expanduser("~/.local-phone-tracker")
        os.makedirs(fallback_dir, exist_ok=True)
        DB_PATH = os.path.join(fallback_dir, "tracker.db")
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                model TEXT DEFAULT 'Unknown Android',
                os_version TEXT DEFAULT 'Android',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS location_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                accuracy_meters REAL,
                altitude REAL,
                speed REAL,
                heading REAL,
                battery_level INTEGER,
                battery_charging INTEGER,
                network_type TEXT,
                event_type TEXT DEFAULT 'periodic',
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_loc_device_time ON location_history(device_id, recorded_at DESC)")
        conn.commit()

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class TrackerRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def _send_json(self, status: int, data: dict):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def _authenticate_device(self, body):
        auth_header = self.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif body and "token" in body:
            token = body["token"]

        if not token:
            return None

        h = hash_token(token)
        with get_db() as conn:
            device = conn.execute("SELECT * FROM devices WHERE token_hash = ?", (h,)).fetchone()
            return dict(device) if device else None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self._send_json(200, {
                "status": "online",
                "local_ip": get_local_ip(),
                "time": datetime.now(timezone.utc).isoformat(),
                "storage": "local SQLite (no cloud)",
                "features": [
                    "Real-time GPS updates",
                    "Last known location & timestamp when powered off",
                    "Critical battery pre-shutdown snapshot",
                    "Anti-theft fake shutdown mode detection"
                ]
            })
            return

        if path == "/api/devices":
            with get_db() as conn:
                devices = conn.execute("SELECT * FROM devices ORDER BY registered_at DESC").fetchall()
                results = []
                now = time.time()
                for dev in devices:
                    dev_id = dev["device_id"]
                    loc = conn.execute(
                        "SELECT * FROM location_history WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                        (dev_id,)
                    ).fetchone()
                    
                    last_seen_epoch = 0
                    if dev["last_seen_at"]:
                        try:
                            dt = datetime.fromisoformat(dev["last_seen_at"].replace("Z", "+00:00"))
                            last_seen_epoch = dt.timestamp()
                        except Exception:
                            pass

                    diff_seconds = now - last_seen_epoch if last_seen_epoch > 0 else 999999
                    if diff_seconds < 90:
                        status = "active"
                    elif diff_seconds < 300:
                        status = "idle"
                    else:
                        status = "offline"

                    item = {
                        "device_id": dev["device_id"],
                        "name": dev["name"],
                        "model": dev["model"],
                        "os_version": dev["os_version"],
                        "registered_at": dev["registered_at"],
                        "last_seen_at": dev["last_seen_at"],
                        "status": status,
                        "offline_duration_seconds": int(diff_seconds) if status == "offline" else 0,
                        "last_known_location": dict(loc) if loc else None
                    }
                    results.append(item)

                self._send_json(200, {"devices": results})
                return

        if path.startswith("/api/devices/") and path.endswith("/history"):
            parts = path.split("/")
            if len(parts) >= 4:
                dev_id = parts[3]
                with get_db() as conn:
                    rows = conn.execute(
                        "SELECT * FROM location_history WHERE device_id = ? ORDER BY id DESC LIMIT 100",
                        (dev_id,)
                    ).fetchall()
                    self._send_json(200, {
                        "device_id": dev_id,
                        "history": [dict(r) for r in reversed(rows)]
                    })
                    return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if body is None:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        if path == "/api/register":
            name = body.get("name", "").strip() or "My Android Phone"
            model = body.get("model", "Android Device").strip()
            os_version = body.get("os_version", "Android 14+").strip()

            device_id = "dev_" + secrets.token_hex(6)
            token = "tk_" + secrets.token_urlsafe(24)
            t_hash = hash_token(token)

            with get_db() as conn:
                conn.execute(
                    "INSERT INTO devices (device_id, name, token_hash, model, os_version, registered_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (device_id, name, t_hash, model, os_version, datetime.now(timezone.utc).isoformat())
                )
                conn.commit()

            self._send_json(201, {
                "message": "Device registered successfully",
                "device_id": device_id,
                "token": token,
                "note": "Store this token securely in your companion app. It is required to authenticate GPS updates."
            })
            return

        if path == "/api/location":
            device = self._authenticate_device(body)
            if not device:
                self._send_json(401, {"error": "Unauthorized. Provide a valid Bearer token."})
                return

            try:
                lat = float(body.get("latitude"))
                lon = float(body.get("longitude"))
            except (TypeError, ValueError):
                self._send_json(400, {"error": "Valid latitude and longitude are required."})
                return

            accuracy = body.get("accuracy_meters")
            altitude = body.get("altitude")
            speed = body.get("speed")
            heading = body.get("heading")
            battery_level = body.get("battery_level")
            battery_charging = 1 if body.get("battery_charging") else 0
            network_type = body.get("network_type", "wifi")
            event_type = body.get("event_type", "periodic")
            recorded_at = body.get("timestamp") or datetime.now(timezone.utc).isoformat()

            dev_id = device["device_id"]
            now_iso = datetime.now(timezone.utc).isoformat()

            with get_db() as conn:
                conn.execute("""
                    INSERT INTO location_history 
                    (device_id, latitude, longitude, accuracy_meters, altitude, speed, heading, battery_level, battery_charging, network_type, event_type, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (dev_id, lat, lon, accuracy, altitude, speed, heading, battery_level, battery_charging, network_type, event_type, recorded_at))
                
                conn.execute("UPDATE devices SET last_seen_at = ? WHERE device_id = ?", (now_iso, dev_id))
                conn.commit()

            self._send_json(200, {
                "status": "success",
                "device_id": dev_id,
                "event_type": event_type,
                "message": "Location telemetry stored locally"
            })
            return

        self._send_json(404, {"error": "Not found"})

def run_server(port=8000):
    init_db()
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, TrackerRequestHandler)
    local_ip = get_local_ip()
    print(f"=" * 65)
    print(f"LOCAL-FIRST PHONE TRACKER & RECOVERY DASHBOARD RUNNING")
    print(f"=" * 65)
    print(f"Local Dashboard (on this laptop): http://localhost:{port}")
    print(f"Phone Companion URL (same Wi-Fi): http://{local_ip}:{port}/mobile.html")
    print(f"Database File: {DB_PATH}")
    print(f"=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server cleanly.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
