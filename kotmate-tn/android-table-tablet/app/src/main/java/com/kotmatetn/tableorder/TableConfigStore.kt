package com.kotmatetn.tableorder

import android.content.Context

/** The entire state of this app is just "which table URL am I pinned to" — set once by
 * staff scanning that table's own printed QR, then remembered locally until someone
 * deliberately re-scans a different one (the tablet physically moved to another table,
 * or the table's QR was regenerated).
 */
class TableConfigStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var tableUrl: String?
        get() = prefs.getString(KEY_URL, null)
        set(value) = prefs.edit().putString(KEY_URL, value).apply()

    fun clear() {
        prefs.edit().remove(KEY_URL).apply()
    }

    private companion object {
        const val PREFS_NAME = "kotmate_table_tablet"
        const val KEY_URL = "table_url"
    }
}
