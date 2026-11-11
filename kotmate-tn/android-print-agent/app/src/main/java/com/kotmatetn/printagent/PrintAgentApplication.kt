package com.kotmatetn.printagent

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.kotmatetn.printagent.printer.PrinterRepository

class PrintAgentApplication : Application() {

    // One shared instance for the whole process — MainActivity's edits must be visible
    // to the running PrintAgentService immediately, with no IPC/restart needed, since
    // both just read this same in-memory object.
    lateinit var printerRepository: PrinterRepository
        private set

    override fun onCreate() {
        super.onCreate()
        printerRepository = PrinterRepository(this)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    companion object {
        const val NOTIFICATION_CHANNEL_ID = "print_agent_service"
    }
}
