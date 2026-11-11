package com.kotmatetn.printagent.server

import android.util.Base64
import android.util.Log
import com.kotmatetn.printagent.printer.PrinterConnectionManager
import com.kotmatetn.printagent.printer.PrinterRepository
import fi.iki.elonen.NanoHTTPD
import org.json.JSONObject

/** The Android twin of `print-agent/agent.py` — same two endpoints, same request/response
 * shapes, same CORS behavior (including Chrome's Private Network Access preflight for a
 * public HTTPS page calling this loopback server), so KOTMate's existing
 * `local_agent`-connection frontend code (lib/printAgent.ts) talks to this unmodified.
 */
class PrintHttpServer(
    port: Int,
    private val repository: PrinterRepository,
    private val connections: PrinterConnectionManager,
) : NanoHTTPD(port) {

    override fun serve(session: IHTTPSession): Response {
        val response = when {
            session.method == Method.OPTIONS -> handleOptions(session)
            session.method == Method.GET && session.uri == "/health" -> json(
                200,
                JSONObject().put("status", "ok").put("agent", "kotmate-print-agent-android"),
            )
            session.method == Method.POST && session.uri == "/print" -> handlePrint(session)
            else -> json(404, JSONObject().put("detail", "not found"))
        }
        return withCors(response)
    }

    private fun handleOptions(session: IHTTPSession): Response {
        val response = newFixedLengthResponse(Response.Status.NO_CONTENT, "text/plain", "")
        response.addHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        response.addHeader("Access-Control-Allow-Headers", "Content-Type")
        // NanoHTTPD normally lowercases header names itself while parsing, but looking
        // this up case-insensitively costs nothing and removes any dependence on that
        // internal detail — a missed Private Network Access header here means Chrome
        // silently blocks every print from a public HTTPS page (exactly the bug this
        // already-shipped header avoids on the Windows agent, see print-agent/agent.py).
        val requestsPrivateNetwork = session.headers.entries.any {
            it.key.equals("access-control-request-private-network", ignoreCase = true) &&
                it.value.equals("true", ignoreCase = true)
        }
        if (requestsPrivateNetwork) {
            response.addHeader("Access-Control-Allow-Private-Network", "true")
        }
        return response
    }

    private fun handlePrint(session: IHTTPSession): Response {
        val body = try {
            readBody(session)
        } catch (e: Exception) {
            return json(400, JSONObject().put("detail", "Invalid request: ${e.message}"))
        }

        val printerName: String
        val dataBase64: String
        try {
            printerName = body.getString("printer_name")
            dataBase64 = body.getString("data_base64")
        } catch (e: Exception) {
            return json(400, JSONObject().put("detail", "Invalid request: ${e.message}"))
        }

        val printer = repository.printers.firstOrNull { it.name == printerName }
            ?: return json(400, JSONObject().put("detail", "No printer named '$printerName' is configured here"))

        val data = try {
            Base64.decode(dataBase64, Base64.DEFAULT)
        } catch (e: Exception) {
            return json(400, JSONObject().put("detail", "Invalid request: bad base64 data"))
        }

        return try {
            connections.send(printer, data)
            json(200, JSONObject().put("status", "printed").put("printer_name", printerName).put("bytes", data.size))
        } catch (e: Exception) {
            Log.w(TAG, "Print failed for '$printerName'", e)
            // The caller (lib/printAgent.ts) only ever checks `res.ok` and reads the JSON
            // `detail` string — it doesn't branch on the exact status code — so a plain
            // 500 here is equivalent to agent.py's 502 as far as the frontend is concerned.
            json(500, JSONObject().put("detail", "Print failed: ${e.message}"))
        }
    }

    private fun readBody(session: IHTTPSession): JSONObject {
        val files = HashMap<String, String>()
        session.parseBody(files)
        val raw = files["postData"] ?: "{}"
        return JSONObject(raw)
    }

    private fun json(status: Int, payload: JSONObject): Response =
        newFixedLengthResponse(statusOf(status), "application/json", payload.toString())

    private fun statusOf(code: Int): Response.IStatus = when (code) {
        200 -> Response.Status.OK
        400 -> Response.Status.BAD_REQUEST
        404 -> Response.Status.NOT_FOUND
        else -> Response.Status.INTERNAL_ERROR
    }

    private fun withCors(response: Response): Response {
        response.addHeader("Access-Control-Allow-Origin", "*")
        return response
    }

    private companion object {
        const val TAG = "PrintHttpServer"
    }
}
