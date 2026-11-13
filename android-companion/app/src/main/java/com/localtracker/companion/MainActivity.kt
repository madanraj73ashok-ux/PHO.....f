package com.localtracker.companion

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var etServerUrl: EditText
    private lateinit var etToken: EditText
    private lateinit var etInterval: EditText
    private lateinit var cbConsent: CheckBox
    private lateinit var btnStart: Button
    private lateinit var btnStop: Button
    private lateinit var tvStatus: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etServerUrl = findViewById(R.id.etServerUrl)
        etToken = findViewById(R.id.etToken)
        etInterval = findViewById(R.id.etInterval)
        cbConsent = findViewById(R.id.cbConsent)
        btnStart = findViewById(R.id.btnStart)
        btnStop = findViewById(R.id.btnStop)
        tvStatus = findViewById(R.id.tvStatus)

        // Restore saved settings from SharedPreferences
        val prefs = getSharedPreferences("tracker_prefs", MODE_PRIVATE)
        etServerUrl.setText(prefs.getString("server_url", "http://192.168.1.50:8000"))
        etToken.setText(prefs.getString("token", ""))
        etInterval.setText(prefs.getInt("interval", 30).toString())

        btnStart.setOnClickListener {
            if (!cbConsent.isChecked) {
                Toast.makeText(this, "Consent authorization is required to start tracking.", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            checkPermissionsAndStart()
        }

        btnStop.setOnClickListener {
            stopTrackingService()
        }

        updateUIState()
    }

    private fun checkPermissionsAndStart() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 101)
        } else {
            startTrackingService()
        }
    }

    private fun startTrackingService() {
        val url = etServerUrl.text.toString().trim()
        val token = etToken.text.toString().trim()
        val interval = etInterval.text.toString().toIntOrNull() ?: 30

        if (url.isEmpty() || token.isEmpty()) {
            Toast.makeText(this, "Please enter both Server URL and Device Token.", Toast.LENGTH_SHORT).show()
            return
        }

        // Save preferences
        getSharedPreferences("tracker_prefs", MODE_PRIVATE).edit()
            .putString("server_url", url)
            .putString("token", token)
            .putInt("interval", interval)
            .apply()

        val intent = Intent(this, TrackingService::class.java).apply {
            putExtra(TrackingService.EXTRA_SERVER_URL, url)
            putExtra(TrackingService.EXTRA_TOKEN, token)
            putExtra(TrackingService.EXTRA_INTERVAL, interval)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        updateUIState()
        tvStatus.text = "Status: Tracking Service Active (Updating every ${interval}s)"
        tvStatus.setTextColor(0xFF22C55E.toInt())
    }

    private fun stopTrackingService() {
        val intent = Intent(this, TrackingService::class.java)
        stopService(intent)
        cbConsent.isChecked = false
        updateUIState()
        tvStatus.text = "Status: Service Stopped (Consent Revoked)"
        tvStatus.setTextColor(0xFFEF4444.toInt())
    }

    private fun updateUIState() {
        val running = TrackingService.isRunning
        btnStart.visibility = if (running) View.GONE else View.VISIBLE
        btnStop.visibility = if (running) View.VISIBLE else View.GONE
        etServerUrl.isEnabled = !running
        etToken.isEnabled = !running
        etInterval.isEnabled = !running
        cbConsent.isEnabled = !running
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 101 && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            startTrackingService()
        } else {
            Toast.makeText(this, "Location permission is required for device recovery.", Toast.LENGTH_LONG).show()
        }
    }
}
