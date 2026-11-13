package com.localtracker.companion

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * BroadcastReceiver triggered immediately when:
 * 1. Battery reaches critically low level (ACTION_BATTERY_LOW)
 * 2. System shutdown is initiated (ACTION_SHUTDOWN / QUICKBOOT_POWEROFF)
 *
 * Sends a high-accuracy emergency pre-shutdown location snapshot to the local server
 * before the device completely loses power.
 */
class ShutdownReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        Log.i("ShutdownReceiver", "Received power event action: $action")

        val eventType = when (action) {
            Intent.ACTION_SHUTDOWN, "android.intent.action.QUICKBOOT_POWEROFF" -> "shutdown_imminent"
            Intent.ACTION_BATTERY_LOW -> "critical_battery"
            else -> "periodic"
        }

        val serviceIntent = Intent(context, TrackingService::class.java).apply {
            this.action = TrackingService.ACTION_SEND_EMERGENCY_SNAPSHOT
            putExtra("EVENT_TYPE", eventType)
        }
        try {
            context.startForegroundService(serviceIntent)
        } catch (e: Exception) {
            Log.e("ShutdownReceiver", "Failed to start emergency tracking service", e)
        }
    }
}
