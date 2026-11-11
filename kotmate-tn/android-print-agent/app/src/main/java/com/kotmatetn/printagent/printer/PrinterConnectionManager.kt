package com.kotmatetn.printagent.printer

import android.hardware.usb.UsbManager
import com.kotmatetn.printagent.printer.connection.BluetoothPrinterConnection
import com.kotmatetn.printagent.printer.connection.PrinterConnection
import com.kotmatetn.printagent.printer.connection.UsbPrinterConnection
import com.kotmatetn.printagent.printer.connection.WifiPrinterConnection
import java.util.concurrent.ConcurrentHashMap

/** Keeps one live connection per configured printer, reused across jobs rather than
 * reconnecting every print (Bluetooth pairing/handshake in particular is slow enough
 * that doing it per-job would make every print feel sluggish). A failed write drops the
 * stale connection so the *next* job reconnects cleanly instead of wedging forever.
 */
class PrinterConnectionManager(private val usbManager: UsbManager) {

    private val connections = ConcurrentHashMap<String, PrinterConnection>()

    @Throws(Exception::class)
    fun send(printer: PrinterConfig, data: ByteArray) {
        val connection = connections.getOrPut(printer.id) { buildConnection(printer) }
        try {
            if (!connection.isConnected()) connection.connect()
            connection.write(data)
        } catch (e: Exception) {
            connection.close()
            connections.remove(printer.id)
            throw e
        }
    }

    fun forget(printerId: String) {
        connections.remove(printerId)?.close()
    }

    fun closeAll() {
        connections.values.forEach { it.close() }
        connections.clear()
    }

    private fun buildConnection(printer: PrinterConfig): PrinterConnection = when (printer.type) {
        PrinterType.BLUETOOTH -> BluetoothPrinterConnection(
            printer.bluetoothAddress ?: error("Printer '${printer.name}' has no paired Bluetooth address"),
        )
        PrinterType.USB -> UsbPrinterConnection(
            usbManager,
            printer.usbVendorId ?: error("Printer '${printer.name}' has no USB vendor id"),
            printer.usbProductId ?: error("Printer '${printer.name}' has no USB product id"),
        )
        PrinterType.WIFI -> WifiPrinterConnection(
            printer.wifiHost ?: error("Printer '${printer.name}' has no WiFi host"),
            printer.wifiPort,
        )
    }
}
