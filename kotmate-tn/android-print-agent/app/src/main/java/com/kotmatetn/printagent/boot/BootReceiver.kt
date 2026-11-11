package com.kotmatetn.printagent.boot

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.kotmatetn.printagent.service.PrintAgentService

/** Mirrors the Windows print-agent's own auto-start-at-login installer behavior
 * (print-agent/installer/) — a counter/table device should have printing working the
 * instant it powers on, with nobody needing to remember to open this app first.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            PrintAgentService.start(context)
        }
    }
}
