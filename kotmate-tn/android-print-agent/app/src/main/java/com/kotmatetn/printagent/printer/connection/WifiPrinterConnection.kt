package com.kotmatetn.printagent.printer.connection

import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket

/** A plain raw-TCP ESC/POS printer on the same LAN as this device (port 9100 is the
 * near-universal "JetDirect"/raw-printing port these printers listen on) — the same
 * "network/wifi" connection concept the backend already uses when it can reach a
 * printer directly (CLAUDE.md §10), except here it's reachable on this tablet's own
 * local WiFi, not from KOTMate's cloud-hosted server, which is exactly why this agent
 * needs to be the one to send it.
 */
class WifiPrinterConnection(private val host: String, private val port: Int) : PrinterConnection {

    @Volatile
    private var socket: Socket? = null
    private var out: OutputStream? = null

    @Synchronized
    override fun connect() {
        if (socket?.isConnected == true && socket?.isClosed == false) return
        val socket = Socket()
        socket.connect(InetSocketAddress(host, port), CONNECT_TIMEOUT_MS)
        this.socket = socket
        this.out = socket.getOutputStream()
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

    override fun isConnected(): Boolean = socket?.let { it.isConnected && !it.isClosed } ?: false

    private companion object {
        const val CONNECT_TIMEOUT_MS = 5_000
    }
}
