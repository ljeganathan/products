package com.kotmatetn.printagent.printer.connection

import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager

/** A USB (OTG) thermal printer. Android's USB Host permission model means this must be
 * granted interactively first (MainActivity's `requestPermission` flow) — by the time
 * this class is used, `UsbManager.hasPermission(device)` is assumed already true;
 * `connect()` still fails loudly rather than silently if that assumption ever breaks
 * (e.g. the user revoked it, or the printer was unplugged and replugged as a new node).
 */
class UsbPrinterConnection(
    private val usbManager: UsbManager,
    private val vendorId: Int,
    private val productId: Int,
) : PrinterConnection {

    @Volatile
    private var connection: UsbDeviceConnection? = null
    private var iface: UsbInterface? = null
    private var endpoint: UsbEndpoint? = null

    @Synchronized
    override fun connect() {
        if (connection != null) return
        val device = usbManager.deviceList.values.firstOrNull {
            it.vendorId == vendorId && it.productId == productId
        } ?: error("USB printer (vendor=$vendorId, product=$productId) isn't attached")

        if (!usbManager.hasPermission(device)) {
            error("No USB permission for this printer yet — reopen it from the printer list")
        }

        // Most ESC/POS USB printers expose a single bulk-OUT endpoint, either under the
        // standard USB Printer class (7) or a vendor-specific one for generic boards —
        // take whichever interface actually has one rather than assuming a fixed class.
        var foundInterface: UsbInterface? = null
        var foundEndpoint: UsbEndpoint? = null
        for (i in 0 until device.interfaceCount) {
            val candidate = device.getInterface(i)
            for (e in 0 until candidate.endpointCount) {
                val endpoint = candidate.getEndpoint(e)
                if (endpoint.direction == UsbConstants.USB_DIR_OUT &&
                    endpoint.type == UsbConstants.USB_ENDPOINT_XFER_BULK
                ) {
                    foundInterface = candidate
                    foundEndpoint = endpoint
                    break
                }
            }
            if (foundEndpoint != null) break
        }
        val usbInterface = foundInterface ?: error("No bulk-OUT endpoint found on this USB printer")
        val usbEndpoint = foundEndpoint ?: error("No bulk-OUT endpoint found on this USB printer")

        val deviceConnection = usbManager.openDevice(device) ?: error("Couldn't open the USB printer")
        if (!deviceConnection.claimInterface(usbInterface, true)) {
            deviceConnection.close()
            error("Couldn't claim the USB printer's interface")
        }

        connection = deviceConnection
        iface = usbInterface
        endpoint = usbEndpoint
    }

    @Synchronized
    override fun write(data: ByteArray) {
        val deviceConnection = connection ?: error("Not connected")
        val usbEndpoint = endpoint ?: error("Not connected")
        // Large bills/reports can exceed a single USB transfer's practical size on some
        // controllers — chunk defensively rather than assume one bulkTransfer call
        // always covers the whole payload.
        var offset = 0
        while (offset < data.size) {
            val length = minOf(CHUNK_SIZE, data.size - offset)
            val sent = deviceConnection.bulkTransfer(usbEndpoint, data, offset, length, WRITE_TIMEOUT_MS)
            if (sent < 0) error("USB write failed at byte offset $offset")
            offset += sent
        }
    }

    @Synchronized
    override fun close() {
        runCatching { iface?.let { connection?.releaseInterface(it) } }
        runCatching { connection?.close() }
        connection = null
        iface = null
        endpoint = null
    }

    override fun isConnected(): Boolean = connection != null

    private companion object {
        const val CHUNK_SIZE = 4096
        const val WRITE_TIMEOUT_MS = 5_000
    }
}
