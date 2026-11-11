package com.kotmatetn.printagent.printer

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** The agent's whole configuration is just this one list, persisted as a single JSON
 * blob in SharedPreferences — there's no multi-user/multi-tenant concept here at all,
 * this app only ever serves whichever printers are physically attached to this one
 * device.
 */
class PrinterRepository(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var printers by mutableStateOf(loadFromPrefs())
        private set

    fun add(printer: PrinterConfig) {
        printers = printers + printer
        persist()
    }

    fun update(printer: PrinterConfig) {
        printers = printers.map { if (it.id == printer.id) printer else it }
        persist()
    }

    fun remove(id: String) {
        printers = printers.filterNot { it.id == id }
        persist()
    }

    fun agentPort(): Int = prefs.getInt(KEY_PORT, DEFAULT_PORT)

    fun setAgentPort(port: Int) {
        prefs.edit().putInt(KEY_PORT, port).apply()
    }

    private fun loadFromPrefs(): List<PrinterConfig> =
        PrinterConfig.listFromJson(prefs.getString(KEY_PRINTERS, null))

    private fun persist() {
        prefs.edit().putString(KEY_PRINTERS, PrinterConfig.listToJson(printers)).apply()
    }

    companion object {
        private const val PREFS_NAME = "kotmate_print_agent"
        private const val KEY_PRINTERS = "printers"
        private const val KEY_PORT = "agent_port"
        const val DEFAULT_PORT = 9123
    }
}
