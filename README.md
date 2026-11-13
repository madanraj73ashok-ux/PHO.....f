# Local-First Phone Recovery & Real-Time Tracking Platform

A 100% local, privacy-focused phone tracking and recovery system. All device telemetry, GPS coordinates, battery status, and location history are stored strictly in a local SQLite database on your own laptop or local server. Zero third-party cloud backends, zero external database servers, and zero telemetry leakage.

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Local-First Phone Tracker Dashboard" width="100%">
</p>

---

## Technical Feasibility & The "Switched-Off Phone / IMEI" Reality

### Why IMEI Alone Cannot Locate a Phone
1. **IMEI is a Cellular Hardware Identifier, Not a GPS Beacon:** An IMEI (International Mobile Equipment Identity) is only registered with cellular base station controllers when a phone connects to a cellular tower. Only licensed telecom carriers and law enforcement with legal warrants can access cell tower triangulation records.
2. **Modern Android Security (Android 10+):** Ordinary Android apps cannot access hardware IMEI. `getImei()` requires privileged carrier permissions or system-level root (`READ_PRIVILEGED_PHONE_STATE`).
3. **True Hardware Power-Off:** When a mobile device is genuinely powered down:
   - The primary CPU, baseband processor, cellular modem, and GPS receiver lose electrical power.
   - The phone cannot calculate satellite fixes or transmit radio packets.
   - *(Note: Apple's Find My and Google's 2024+ Find My Device rely on specialized Ultra-Low-Power Bluetooth hardware and an encrypted crowd-sourced mesh of nearby active devices—not direct IMEI or standalone GPS).*

### How This Platform Solves Recovery When Switched Off
1. **Last Known Position & Timestamp Preservation:** The server preserves the exact location, timestamp, battery level, and network type received prior to the device going offline. If the phone is powered down, the dashboard immediately highlights the offline state and pins the last known position.
2. **Critical Battery Pre-Shutdown Snapshot (⚡):** When battery level drops to critical (<= 5%) or before the OS completes shutdown (`ACTION_SHUTDOWN`), the companion app automatically captures and delivers a high-accuracy GPS fix so you know where it was right before it turned off.
3. **Anti-Theft "Fake Shutdown" Mode (🛡️):** If stolen or confiscated, the phone can be placed into Fake Shutdown mode. It displays an authentic "Power off / Shutting down..." dialog, then completely blacks out the screen (ultra-dim OLED black) while secretly keeping the background GPS service active and streaming coordinates every 10 seconds. Four rapid taps on the screen exit the mode.

---

## System Architecture

```
[ Android Device (Companion App / Mobile Web) ]
                     │
       Periodic GPS / Battery Updates (Bearer Auth)
       Pre-Shutdown Snapshots (ACTION_SHUTDOWN)
       Anti-Theft Stealth Stream (Fake Shutdown)
                     ▼
[ Local Python HTTP Server (server.py) ]
                     │
       SQLite Local Storage (tracker.db)
                     ▼
[ Local Web Dashboard (http://localhost:8000) ]
       Leaflet OpenStreetMap View + Device Health + History Trail
```

---

## Local Server Deployment & Testing Guide

### 1. One-Command Server Deployment
No external dependencies are required. The server uses Python's standard library (`http.server` and `sqlite3`).

```bash
# Clone the repository
git clone https://github.com/madanraj73ashok-ux/PHO.....f.git
cd PHO.....f

# Deploy and start on default port 8000
./run_local.sh

# Or run directly via Python (specify custom port if desired):
python3 server.py 8000
```

When started, your terminal displays:
```text
=================================================================
LOCAL-FIRST PHONE TRACKER & RECOVERY DASHBOARD RUNNING
=================================================================
Local Dashboard (on this laptop): http://localhost:8000
Phone Companion URL (same Wi-Fi): http://192.168.1.X:8000/mobile.html
Database File: .../tracker.db
=================================================================
```

Open **`http://localhost:8000`** in your browser to view the live dashboard.

---

### 2. Run Automated Verification Tests
Run the comprehensive 9-point unit test suite that validates server health, device registration, token authentication, location ingestion, simulated offline recovery, pre-shutdown snapshots, and stealth alerts:

```bash
python3 tests/test_tracker.py
```

Expected output:
```text
test_01_server_status ... ok
test_02_device_registration ... ok
test_03_unauthorized_location_rejected ... ok
test_04_authorized_location_ingestion ... ok
test_05_device_status_and_last_known_location ... ok
test_06_simulated_switched_off_offline_preservation ... ok
test_07_location_history_trail ... ok
test_08_critical_battery_pre_shutdown_event ... ok
test_09_fake_shutdown_active_event ... ok

Ran 9 tests in 0.74s - OK
```

---

### 3. Instant Telemetry Simulator (Test Without a Physical Phone)
To test the real-time dashboard and map rendering immediately without an Android phone, run the built-in simulator:

```bash
# In a separate terminal tab:
python3 scripts/simulate_device.py
```

This simulator automatically:
1. Registers a simulated test phone (`Simulated Pixel 8 Pro`).
2. Transmits movement GPS coordinates, battery percentage, and Wi-Fi/Cellular telemetry.
3. Fires a **Critical Battery Pre-Shutdown Snapshot** event (`critical_battery_shutdown`).
4. Verifies database persistence and updates the dashboard live at `http://localhost:8000`.

---

### 4. Manual Testing via cURL

You can also test the local server API directly via standard HTTP requests:

#### Step A: Register a Device
```bash
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Phone", "model": "Pixel 8 Pro", "os_version": "Android 15"}'
```
Response:
```json
{
  "message": "Device registered successfully",
  "device_id": "dev_a1b2c3d4e5f6",
  "token": "tk_YourSecretBearerTokenHere..."
}
```

#### Step B: Send GPS Telemetry
```bash
curl -X POST http://localhost:8000/api/location \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer tk_YourSecretBearerTokenHere..." \
  -d '{
    "latitude": 37.7749,
    "longitude": -122.4194,
    "accuracy": 4.5,
    "battery_level": 82,
    "is_charging": false,
    "network_type": "wifi",
    "network_name": "Home_Fiber_5G",
    "event_type": "periodic"
  }'
```

#### Step C: Simulate Critical Battery Pre-Shutdown Snapshot
```bash
curl -X POST http://localhost:8000/api/location \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer tk_YourSecretBearerTokenHere..." \
  -d '{
    "latitude": 37.7788,
    "longitude": -122.4145,
    "accuracy": 5.0,
    "battery_level": 3,
    "is_charging": false,
    "network_type": "cellular",
    "network_name": "LTE",
    "event_type": "critical_battery_shutdown"
  }'
```

#### Step D: Simulate Anti-Theft Fake Shutdown Event
```bash
curl -X POST http://localhost:8000/api/location \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer tk_YourSecretBearerTokenHere..." \
  -d '{
    "latitude": 37.7810,
    "longitude": -122.4120,
    "accuracy": 3.0,
    "battery_level": 45,
    "is_charging": false,
    "network_type": "cellular",
    "network_name": "5G Ultra",
    "event_type": "fake_shutdown_active"
  }'
```

---

### 5. Pairing a Real Mobile Device

#### Option A: Instant Web Companion (Browser-Based, No Install)
1. Open the companion URL on your phone's browser (or scan the QR code from the dashboard):
   `http://<YOUR_LAPTOP_IP>:8000/mobile.html`
2. Enter your Device ID and Token (auto-filled if opened from QR).
3. Tap **"Grant Consent & Start Tracking"** and allow browser location permissions.
4. Your phone is now streaming live coordinates, battery percentage, and network status to your laptop.

#### Option B: Native Android Studio App (Background Service & Broadcast Receiver)
1. Open the `android-companion` directory in Android Studio.
2. Build and install the APK to your Android device (`app/src/main`).
3. Enter your laptop's local server IP and authentication token.
4. Tap **"Start Background Service"**.
5. The foreground tracking service and `ShutdownReceiver` will automatically capture pre-shutdown snapshots upon low battery or system shutdown.

---

## API Reference

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/status` | Server health, local IP address, and database status | No |
| `POST` | `/api/register` | Registers device, returns unique ID & secure token | No |
| `GET` | `/api/devices` | Lists registered devices with live/offline status and last known location | No |
| `POST` | `/api/location` | Ingests GPS coordinates, battery, network, and event telemetry | Bearer Token |
| `GET` | `/api/devices/{id}/history` | Retrieves location history trail (up to 100 points) | No |

---

## License
MIT License. Created for local-first, privacy-preserving device recovery.
