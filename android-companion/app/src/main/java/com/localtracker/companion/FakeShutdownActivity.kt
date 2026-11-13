package com.localtracker.companion

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Toast

/**
 * Anti-Theft Fake Shutdown Activity:
 * Simulates a powered-off black screen while keeping TrackingService running in the background.
 * Prevents screen timeout and dims display completely.
 * Secret exit: 4 rapid taps anywhere on screen within 1.5 seconds.
 */
class FakeShutdownActivity : Activity() {
    private var tapCount = 0
    private var lastTapTime = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
            WindowManager.LayoutParams.FLAG_FULLSCREEN or
            WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD or
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
        )
        window.attributes = window.attributes.apply {
            screenBrightness = 0.01f
        }

        val blackView = View(this).apply {
            setBackgroundColor(0xFF000000.toInt())
            setOnClickListener {
                val now = System.currentTimeMillis()
                if (now - lastTapTime < 500) {
                    tapCount++
                } else {
                    tapCount = 1
                }
                lastTapTime = now

                if (tapCount >= 4) {
                    Toast.makeText(this@FakeShutdownActivity, "Anti-theft mode disengaged", Toast.LENGTH_SHORT).show()
                    finish()
                }
            }
        }
        setContentView(blackView)

        val serviceIntent = Intent(this, TrackingService::class.java).apply {
            action = TrackingService.ACTION_SET_EVENT_MODE
            putExtra("EVENT_TYPE", "fake_shutdown_active")
        }
        try {
            startForegroundService(serviceIntent)
        } catch (e: Exception) {
            // Service already running or fallback
        }
    }

    override fun onBackPressed() {
        // Prevent physical or gesture back button from exiting fake shutdown
    }
}
