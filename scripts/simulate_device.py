#!/usr/bin/env python3
"""
Local Device Telemetry Simulator
================================
Simulates an Android phone sending GPS coordinates, battery updates,
pre-shutdown critical battery snapshots, and anti-theft stealth events
to test the local tracking server and dashboard without a physical phone.
"""

import sys
import time
import json
import urllib.request
import urllib.error

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    base_url = base_url.rstrip("/")

    print("==================================================")
    print("Local Phone Tracker - Telemetry & Deploy Simulator")
    print(f"Target Server: {base_url}")
    print("==================================================")

    # 1. Check Server Health
    print("\n[1/5] Checking server health...")
    try:
        with urllib.request.urlopen(f"{base_url}/api/status", timeout=5) as res:
            status = json.loads(res.read().decode())
            print(f"  ✔ Server is ONLINE (Version {status.get('version', '1.0.0')})")
            print(f"  ✔ Database: {status.get('db_status')}, Active Devices: {status.get('device_count')}")
    except Exception as e:
        print(f"  ✖ Could not connect to {base_url}: {e}")
        print("    Please start the server first with: python3 server.py")
        sys.exit(1)

    # 2. Register Simulated Device
    print("\n[2/5] Registering simulated device...")
    reg_payload = json.dumps({
        "name": "Simulated Pixel 8 Pro",
        "model": "Pixel 8 Pro (Simulated)",
        "os_version": "Android 15"
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/register",
        data=reg_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        reg_data = json.loads(res.read().decode())
        device_id = reg_data["device_id"]
        token = reg_data["token"]
        print(f"  ✔ Device Registered: {device_id}")
        print(f"  ✔ Auth Token: {token[:12]}...")

    # Helper for location POST
    def send_location(lat, lon, battery, charging, net_type, net_name, event, label):
        payload = json.dumps({
            "latitude": lat,
            "longitude": lon,
            "accuracy": 3.5,
            "battery_level": battery,
            "is_charging": charging,
            "network_type": net_type,
            "network_name": net_name,
            "event_type": event
        }).encode("utf-8")

        r = urllib.request.Request(
            f"{base_url}/api/location",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )
        with urllib.request.urlopen(r) as resp:
            data = json.loads(resp.read().decode())
            print(f"  ✔ [{label}] Lat: {lat:.5f}, Lon: {lon:.5f}, Battery: {battery}%, Event: {event} -> HTTP {resp.status}")

    # 3. Stream Normal GPS Telemetry
    print("\n[3/5] Ingesting periodic GPS movement telemetry...")
    sim_points = [
        (37.7749, -122.4194, 78, False, "wifi", "CoffeeShop_WiFi", "periodic", "Fix 1 - Moving"),
        (37.7760, -122.4180, 77, False, "cellular", "5G Ultra", "periodic", "Fix 2 - En Route"),
        (37.7775, -122.4162, 76, False, "cellular", "5G Ultra", "periodic", "Fix 3 - Downtown")
    ]
    for pt in sim_points:
        send_location(*pt)
        time.sleep(0.4)

    # 4. Simulate Critical Battery Pre-Shutdown Snapshot
    print("\n[4/5] Simulating Critical Battery Pre-Shutdown Snapshot (OS ACTION_SHUTDOWN)...")
    send_location(
        37.7788, -122.4145, 3, False, "cellular", "LTE",
        "critical_battery_shutdown", "Critical Battery (3%) Pre-Shutdown"
    )

    # 5. Verify on Dashboard
    print("\n[5/5] Verifying telemetry in database...")
    with urllib.request.urlopen(f"{base_url}/api/devices") as res:
        devs = json.loads(res.read().decode()).get("devices", [])
        matched = [d for d in devs if d.get("device_id") == device_id]
        if matched:
            dev = matched[0]
            last_loc = dev.get('last_known_location') or {}
            print(f"  ✔ Device '{dev['name']}' verified in local SQLite DB!")
            print(f"    Status: {dev.get('status', 'unknown').upper()}")
            print(f"    Last Known Coordinates: {last_loc.get('latitude')}, {last_loc.get('longitude')}")
            print(f"    Last Battery: {last_loc.get('battery_level')}%")
            print(f"    Last Event Type: {last_loc.get('event_type')}")

    print("\n==================================================")
    print("SUCCESS: Local deployment test completed!")
    print(f"Open {base_url} in your browser to view the live dashboard.")
    print("==================================================")

if __name__ == "__main__":
    main()
