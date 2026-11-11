package com.kotmatetn.printagent.service

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.kotmatetn.printagent.MainActivity
import com.kotmatetn.printagent.PrintAgentApplication
import com.kotmatetn.printagent.R
import com.kotmatetn.printagent.printer.PrinterConnectionManager
import com.kotmatetn.printagent.server.PrintHttpServer
import fi.iki.elonen.NanoHTTPD

/** Foreground service holding the local HTTP server + every printer's live connection —
 * the Android equivalent of `print-agent/agent.py` running as a Windows background
 * process. Runs for as long as the device is on; a visible notification is mandatory
 * (Android foreground-service rules) and doubles as "yes, this is working" reassurance
 * for whoever set the tablet up.
 */
class PrintAgentService : Service() {

    private var server: PrintHttpServer? = null
    private var connections: PrinterConnectionManager? = null

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, buildNotification())
        startServer()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // START_STICKY: Android restarts this service after it's killed for memory —
        // an unattended counter/table device must recover its printing capability on
        // its own, not wait for someone to notice and reopen the app.
        return START_STICKY
    }

    override fun onDestroy() {
        server?.stop()
        connections?.closeAll()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startServer() {
        val app = application as PrintAgentApplication
        val usbManager = getSystemService(Context.USB_SERVICE) as UsbManager
        val connectionManager = PrinterConnectionManager(usbManager)
        connections = connectionManager
        val httpServer = PrintHttpServer(app.printerRepository.agentPort(), app.printerRepository, connectionManager)
        httpServer.start(NanoHTTPD.SOCKET_READ_TIMEOUT, false)
        server = httpServer
    }

    private fun buildNotification(): Notification {
        val app = application as PrintAgentApplication
        val openAppIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, PrintAgentApplication.NOTIFICATION_CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notification_running, app.printerRepository.agentPort()))
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setOngoing(true)
            .setContentIntent(openAppIntent)
            .build()
    }

    companion object {
        private const val NOTIFICATION_ID = 1

        fun start(context: Context) {
            val intent = Intent(context, PrintAgentService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, PrintAgentService::class.java))
        }
    }
}
