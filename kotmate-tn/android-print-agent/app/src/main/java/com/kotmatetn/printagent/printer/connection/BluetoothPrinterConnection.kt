package com.kotmatetn.printagent.printer.connection

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothSocket
import java.io.OutputStream
import java.util.UUID

/** Classic Bluetooth (SPP) — the transport almost every thermal receipt printer with a
 * "Bluetooth" badge actually speaks. BLE-only printers aren't handled here; none of the
 * common 58mm/80mm ESC/POS printers this app targets use BLE.
 */
class BluetoothPrinterConnection(private val address: String) : PrinterConnection {

    @Volatile
    private var socket: BluetoothSocket? = null
    private var out: OutputStream? = null

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT is checked before any printer
    // using this class is ever reachable — see MainActivity's permission gate.
    @Synchronized
    override fun connect() {
        if (socket?.isConnected == true) return
        val adapter = BluetoothAdapter.getDefaultAdapter()
            ?: error("This device has no Bluetooth adapter")
        val device = adapter.getRemoteDevice(address)
        // The standard Serial Port Profile UUID — every SPP-mode thermal printer accepts
        // a raw byte stream over this same well-known channel.
        val socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
        adapter.cancelDiscovery()
        socket.connect()
        this.socket = socket
        this.out = socket.outputStream
    }

    @Synchronized
    override fun write(data: ByteArray) {
        val stream = out ?: error("Not connected")
        stream.write(data)
        stream.flush()
    }

    @Synchronized
    override fun close() {
        runCatching { out?.close() }
        runCatching { socket?.close() }
        out = null
        socket = null
    }

    override fun isConnected(): Boolean = socket?.isConnected == true

    private companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }
}
