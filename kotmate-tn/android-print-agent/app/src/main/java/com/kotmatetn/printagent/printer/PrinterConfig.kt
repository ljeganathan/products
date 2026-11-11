package com.kotmatetn.printagent.printer

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/** How this one printer is physically reached. Mirrors the three transports the agent
 * supports — never "rawbt", since that's a different Android app's own job; this agent
 * replaces it precisely because RawBT only remembers a single default printer.
 */
enum class PrinterType {
    BLUETOOTH,
    USB,
    WIFI,
}

/** One configured physical printer. `name` is what KOTMate's Settings → Printers page
 * calls this printer's "Windows Printer Name" field (reused as a generic printer-name
 * key, not Windows-specific) — the browser sends it back on every `/print` call so this
 * agent knows which live connection to write the rendered bytes to. Names are matched
 * case-sensitively and must be unique within this agent.
 */
data class PrinterConfig(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val type: PrinterType,
    // Bluetooth: the paired device's MAC address (android.bluetooth.BluetoothDevice.address).
    val bluetoothAddress: String? = null,
    // USB: identifies a specific attached device so the right one is reopened after a
    // reconnect, even with more than one USB printer plugged in at once.
    val usbVendorId: Int? = null,
    val usbProductId: Int? = null,
    // WiFi: a raw TCP socket to the printer's own IP, same "network/wifi" ESC/POS
    // convention the backend already uses when it prints directly (CLAUDE.md §10) —
    // port 9100 is the near-universal raw-printing port these printers listen on.
    val wifiHost: String? = null,
    val wifiPort: Int = 9100,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("id", id)
        put("name", name)
        put("type", type.name)
        bluetoothAddress?.let { put("bluetoothAddress", it) }
        usbVendorId?.let { put("usbVendorId", it) }
        usbProductId?.let { put("usbProductId", it) }
        wifiHost?.let { put("wifiHost", it) }
        put("wifiPort", wifiPort)
    }

    companion object {
        fun fromJson(json: JSONObject): PrinterConfig = PrinterConfig(
            id = json.getString("id"),
            name = json.getString("name"),
            type = PrinterType.valueOf(json.getString("type")),
            bluetoothAddress = json.optString("bluetoothAddress").takeIf { it.isNotEmpty() },
            usbVendorId = if (json.has("usbVendorId")) json.getInt("usbVendorId") else null,
            usbProductId = if (json.has("usbProductId")) json.getInt("usbProductId") else null,
            wifiHost = json.optString("wifiHost").takeIf { it.isNotEmpty() },
            wifiPort = json.optInt("wifiPort", 9100),
        )

        fun listToJson(printers: List<PrinterConfig>): String {
            val array = JSONArray()
            printers.forEach { array.put(it.toJson()) }
            return array.toString()
        }

        fun listFromJson(raw: String?): List<PrinterConfig> {
            if (raw.isNullOrBlank()) return emptyList()
            val array = JSONArray(raw)
            return (0 until array.length()).map { fromJson(array.getJSONObject(it)) }
        }
    }
}
