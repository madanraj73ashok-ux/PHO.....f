package com.localtracker.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.*

class TrackingService : Service(), LocationListener {

    private val serviceScope = CoroutineScope(Dispatchers.IO + Job())
    private lateinit var locationManager: LocationManager
    private var serverUrl: String = ""
    private var token: String = ""
    private var intervalMs: Long = 30000L
    private var currentEventType: String = "periodic"


    companion object {
        const val CHANNEL_ID = "local_tracker_channel"
        const val NOTIFICATION_ID = 1001
        const val EXTRA_SERVER_URL = "server_url"
        const val EXTRA_TOKEN = "token"
        const val EXTRA_INTERVAL = "interval_sec"
        var isRunning = false
        const val ACTION_SEND_EMERGENCY_SNAPSHOT = "com.localtracker.companion.ACTION_SEND_EMERGENCY_SNAPSHOT"
        const val ACTION_SET_EVENT_MODE = "com.localtracker.companion.ACTION_SET_EVENT_MODE"

    }

    override fun onCreate() {
        super.onCreate()
        locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        serverUrl = intent?.getStringExtra(EXTRA_SERVER_URL) ?: ""
        token = intent?.getStringExtra(EXTRA_TOKEN) ?: ""
        val intervalSec = intent?.getIntExtra(EXTRA_INTERVAL, 30) ?: 30
        intervalMs = intervalSec * 1000L

        val notification = buildNotification("Active - Streaming GPS to local server")
        startForeground(NOTIFICATION_ID, notification)
        isRunning = true

        
        if (intent?.action == ACTION_SEND_EMERGENCY_SNAPSHOT) {
            currentEventType = intent.getStringExtra("EVENT_TYPE") ?: "shutdown_imminent"
            try {
                val lastGps = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
                    ?: locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
                if (lastGps != null) {
                    sendLocationToServer(lastGps)
                }
            } catch (e: SecurityException) {}
        } else if (intent?.action == ACTION_SET_EVENT_MODE) {
            currentEventType = intent.getStringExtra("EVENT_TYPE") ?: "fake_shutdown_active"
        }

        startLocationUpdates()

        return START_STICKY
    }

    private fun 
        if (intent?.action == ACTION_SEND_EMERGENCY_SNAPSHOT) {
            currentEventType = intent.getStringExtra("EVENT_TYPE") ?: "shutdown_imminent"
            try {
                val lastGps = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
                    ?: locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
                if (lastGps != null) {
                    sendLocationToServer(lastGps)
                }
            } catch (e: SecurityException) {}
        } else if (intent?.action == ACTION_SET_EVENT_MODE) {
            currentEventType = intent.getStringExtra("EVENT_TYPE") ?: "fake_shutdown_active"
        }

        startLocationUpdates()
 {
        try {
            // Request both GPS and Network providers for maximum reliability
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    intervalMs,
                    5f,
                    this
                )
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    intervalMs,
                    10f,
                    this
                )
            }
        } catch (e: SecurityException) {
            Log.e("TrackingService", "Location permission missing", e)
        }
    }

    override fun onLocationChanged(location: Location) {
        serviceScope.launch {
            sendLocationPing(location)
        }
    }

    private fun sendLocationPing(location: Location) {
        try {
            val batteryInfo = getBatteryStatus()
            val netType = getNetworkType()
            val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }

            val payload = JSONObject().apply {
                put("latitude", location.latitude)
                put("longitude", location.longitude)
                put("accuracy_meters", location.accuracy)
                put("altitude", if (location.hasAltitude()) location.altitude else JSONObject.NULL)
                put("speed", if (location.hasSpeed()) location.speed else JSONObject.NULL)
                put("heading", if (location.hasBearing()) location.bearing else JSONObject.NULL)
                put("battery_level", batteryInfo.first)
                put("battery_charging", batteryInfo.second)
                put("network_type", netType)
                put("timestamp", isoFormat.format(Date()))
            }

            val endpoint = if (serverUrl.endsWith("/")) "${serverUrl}api/location" else "$serverUrl/api/location"
            val url = URL(endpoint)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 8000
                readTimeout = 8000
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Authorization", "Bearer $token")
            }

            OutputStreamWriter(conn.outputStream).use { writer ->
                writer.write(payload.toString())
                writer.flush()
            }

            val responseCode = conn.responseCode
            Log.d("TrackingService", "Server response code: $responseCode")
            conn.disconnect()
        } catch (e: Exception) {
            Log.w("TrackingService", "Failed to transmit location ping: ${e.message}")
        }
    }

    private fun getBatteryStatus(): Pair<Int, Boolean> {
        val batteryIntent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = batteryIntent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = batteryIntent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val status = batteryIntent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        val pct = if (level >= 0 && scale > 0) (level * 100 / scale) else -1
        return Pair(pct, isCharging)
    }

    private fun getNetworkType(): String {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val net = cm.activeNetwork ?: return "offline"
        val caps = cm.getNetworkCapabilities(net) ?: return "offline"
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            else -> "other"
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Local Location Tracking",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows active background GPS telemetry transmission"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(status: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Local Tracker Active")
            .setContentText(status)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        locationManager.removeUpdates(this)
        serviceScope.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}
}
