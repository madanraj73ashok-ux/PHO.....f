# Local-First Phone Recovery & Real-Time Tracking Platform

A 100% local, privacy-focused phone tracking and recovery system. All device telemetry, GPS coordinates, battery status, and location history are stored strictly in a local SQLite database on your own laptop or local server. Zero third-party cloud backends, zero external database servers, and zero telemetry leakage.

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

## Quickstart Guide

### 1. Prerequisites
- Python 3.8+ (no third-party Python packages required; uses standard library `http.server` and `sqlite3`).
- A laptop/PC and an Android phone connected to the same local Wi-Fi (or connected via a private Tailscale / WireGuard mesh).

### 2. Start the Local Server
```bash
python3 server.py
```
By default, the server starts on port `8000`. You will see output like:
```text
=================================================================
LOCAL-FIRST PHONE TRACKER & RECOVERY DASHBOARD RUNNING
=================================================================
Local Dashboard (on this laptop): http://localhost:8000
Phone Companion URL (same Wi-Fi): http://192.168.1.X:8000/mobile.html
Database File: .../tracker.db
=================================================================
```

### 3. Open the Dashboard & Register a Phone
1. Open `http://localhost:8000` in your laptop's browser.
2. Click **"+ Register New Device"**.
3. Enter your phone's name (e.g. `Madan's Pixel`) and click **Generate Secure Credentials**.
4. A pairing QR code and unique random Bearer Token will appear.

### 4. Pair Your Phone

#### Option A: Instant Web Companion (No APK installation required)
1. Open the companion URL on your phone's browser (or scan the QR code):
   `http://<YOUR_LAPTOP_IP>:8000/mobile.html`
2. Enter your Device ID and Token (auto-filled if opened from QR).
3. Tap **"Grant Consent & Start Tracking"** and allow location access.
4. Your phone is now actively streaming real-time coordinates, battery level, and connectivity status!

#### Option B: Native Android Studio App (Background & Shutdown Service)
1. Open the `android-companion` directory in Android Studio.
2. Build and install the APK to your device.
3. Open **Local Tracker Companion**, paste your laptop IP and token, and tap **"Start Background Service"**.
4. The background foreground service and `ShutdownReceiver` will maintain tracking even when minimized or when battery is critically low.

---

## API Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/status` | Server health, local IP, and features | No |
| `POST` | `/api/register` | Registers device, returns unique ID & token | No |
| `GET` | `/api/devices` | Lists registered devices with live/offline status | No |
| `POST` | `/api/location` | Ingests GPS, battery, and event telemetry | Bearer Token |
| `GET` | `/api/devices/{id}/history` | Retrieves location history trail (up to 100 points) | No |

---

## Verification & Automated Tests

A comprehensive unit test suite is included to validate registration, unauthorized rejections, telemetry ingestion, offline state preservation, pre-shutdown snapshots, and fake shutdown alerts:
```bash
python3 tests/test_tracker.py
```

---

## License
MIT License. Created for local-first, privacy-preserving device recovery.
