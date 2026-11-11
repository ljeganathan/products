package com.kotmatetn.staffapp

import android.content.Context

/** Just two settings: which server to point at (so the same APK also works against a
 * self-hosted/on-prem deployment, not only the SaaS URL), and whether this particular
 * device should be locked to the app (a dedicated Kiosk/KDS terminal) or left free to
 * switch apps normally (a counter phone/tablet staff also use for other things).
 */
class AppConfigStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_URL, DEFAULT_URL) ?: DEFAULT_URL
        set(value) = prefs.edit().putString(KEY_URL, value).apply()

    var kioskLockEnabled: Boolean
        get() = prefs.getBoolean(KEY_LOCK, false)
        set(value) = prefs.edit().putBoolean(KEY_LOCK, value).apply()

    companion object {
        private const val PREFS_NAME = "kotmate_staff_app"
        private const val KEY_URL = "server_url"
        private const val KEY_LOCK = "kiosk_lock"
        const val DEFAULT_URL = "https://app.kotmatetn.in"
    }
}
