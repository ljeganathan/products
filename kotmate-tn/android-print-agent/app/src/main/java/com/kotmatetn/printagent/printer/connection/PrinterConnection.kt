package com.kotmatetn.printagent.printer.connection

/** A live (or lazily-openable) link to one physical printer. Implementations only ever
 * need to move raw bytes — the backend has already rendered the full ESC/POS (or
 * dot-matrix) byte stream server-side (CLAUDE.md §10), so there is nothing printer-type-
 * aware to do here beyond "write these bytes to this transport."
 */
interface PrinterConnection {
    /** Opens the transport if it isn't already open. Safe to call when already open. */
    @Throws(Exception::class)
    fun connect()

    @Throws(Exception::class)
    fun write(data: ByteArray)

    fun close()

    /** Best-effort liveness check — a failed write should still fall back to a fresh
     * `connect()` on the next job rather than trusting this alone, since a stale socket
     * can look connected until it's actually used.
     */
    fun isConnected(): Boolean
}
