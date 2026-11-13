import unittest
import os
import json
import time
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Import server code
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

class TestLocalPhoneTracker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup temporary isolated test database in /tmp
        cls.test_db = "/tmp/test_tracker_run.db"
        if os.path.exists(cls.test_db):
            os.remove(cls.test_db)
        server.DB_PATH = cls.test_db
        server.init_db()

        # Start server in daemon thread on test port
        cls.port = 8899
        cls.server = server.HTTPServer(("127.0.0.1", cls.port), server.TrackerRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        if os.path.exists(cls.test_db):
            os.remove(cls.test_db)

    def _request(self, path, method="GET", data=None, token=None):
        url = self.base_url + path
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(url, data=json.dumps(data).encode("utf-8") if data else None, headers=headers, method=method)
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_01_server_status(self):
        status, data = self._request("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "online")
        self.assertIn("local SQLite", data["storage"])

    def test_02_device_registration(self):
        payload = {
            "name": "Madan Test Pixel",
            "model": "Google Pixel 8",
            "os_version": "Android 14"
        }
        status, data = self._request("/api/register", method="POST", data=payload)
        self.assertEqual(status, 201)
        self.assertTrue(data["device_id"].startswith("dev_"))
        self.assertTrue(data["token"].startswith("tk_"))
        self.__class__.device_id = data["device_id"]
        self.__class__.token = data["token"]

    def test_03_unauthorized_location_rejected(self):
        payload = {"latitude": 13.0827, "longitude": 80.2707}
        status, data = self._request("/api/location", method="POST", data=payload)
        self.assertEqual(status, 401)
        self.assertIn("Unauthorized", data["error"])

    def test_04_authorized_location_ingestion(self):
        payload = {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "accuracy_meters": 4.5,
            "altitude": 920.0,
            "speed": 1.2,
            "heading": 180.0,
            "battery_level": 82,
            "battery_charging": True,
            "network_type": "wifi",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        status, data = self._request("/api/location", method="POST", data=payload, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")

    def test_05_device_status_and_last_known_location(self):
        status, data = self._request("/api/devices")
        self.assertEqual(status, 200)
        devices = data["devices"]
        self.assertGreaterEqual(len(devices), 1)

        dev = next(d for d in devices if d["device_id"] == self.device_id)
        self.assertEqual(dev["name"], "Madan Test Pixel")
        self.assertEqual(dev["status"], "active")
        self.assertIsNotNone(dev["last_known_location"])
        loc = dev["last_known_location"]
        self.assertAlmostEqual(loc["latitude"], 12.9716, places=4)
        self.assertAlmostEqual(loc["longitude"], 77.5946, places=4)
        self.assertEqual(loc["battery_level"], 82)
        self.assertEqual(loc["battery_charging"], 1)
        self.assertEqual(loc["network_type"], "wifi")

    def test_06_simulated_switched_off_offline_preservation(self):
        # Simulate device switched off 15 minutes ago
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        with server.get_db() as conn:
            conn.execute("UPDATE devices SET last_seen_at = ? WHERE device_id = ?", (past_time, self.device_id))
            conn.commit()

        status, data = self._request("/api/devices")
        self.assertEqual(status, 200)
        dev = next(d for d in data["devices"] if d["device_id"] == self.device_id)
        self.assertEqual(dev["status"], "offline")
        self.assertGreater(dev["offline_duration_seconds"], 800)
        # Even when offline/powered off, last known location and battery level are strictly preserved
        self.assertIsNotNone(dev["last_known_location"])
        self.assertAlmostEqual(dev["last_known_location"]["latitude"], 12.9716, places=4)

    def test_07_location_history_trail(self):
        # Post multiple points
        p2 = {"latitude": 12.9720, "longitude": 77.5950, "battery_level": 81}
        p3 = {"latitude": 12.9730, "longitude": 77.5960, "battery_level": 80}
        self._request("/api/location", method="POST", data=p2, token=self.token)
        self._request("/api/location", method="POST", data=p3, token=self.token)

        status, data = self._request(f"/api/devices/{self.device_id}/history")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(data["history"]), 3)
        self.assertEqual(data["history"][-1]["latitude"], 12.9730)


    def test_08_critical_battery_pre_shutdown_event(self):
        payload = {
            "latitude": 12.9740,
            "longitude": 77.5970,
            "battery_level": 3,
            "battery_charging": False,
            "event_type": "critical_battery",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        status, data = self._request("/api/location", method="POST", data=payload, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(data["event_type"], "critical_battery")

        # Check in devices list
        status, dev_data = self._request("/api/devices")
        dev = next(d for d in dev_data["devices"] if d["device_id"] == self.device_id)
        self.assertEqual(dev["last_known_location"]["event_type"], "critical_battery")
        self.assertEqual(dev["last_known_location"]["battery_level"], 3)

    def test_09_fake_shutdown_active_event(self):
        payload = {
            "latitude": 12.9750,
            "longitude": 77.5980,
            "battery_level": 55,
            "event_type": "fake_shutdown_active",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        status, data = self._request("/api/location", method="POST", data=payload, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(data["event_type"], "fake_shutdown_active")

        status, dev_data = self._request("/api/devices")
        dev = next(d for d in dev_data["devices"] if d["device_id"] == self.device_id)
        self.assertEqual(dev["last_known_location"]["event_type"], "fake_shutdown_active")

if __name__ == "__main__":
    unittest.main(verbosity=2)
