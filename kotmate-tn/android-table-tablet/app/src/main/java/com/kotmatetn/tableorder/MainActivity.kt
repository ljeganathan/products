package com.kotmatetn.tableorder

import android.app.AlertDialog
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.PopupMenu
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

/** The whole app, in one screen: until a table is bound, show the "scan this table's QR"
 * setup prompt; once bound, show nothing but that table's ordering page, full screen,
 * indefinitely. There is deliberately no navigation chrome, URL bar, or way to browse
 * anywhere else — a customer or a passing child could pick up this tablet, and the only
 * thing it should ever be able to do is order from this one table.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var config: TableConfigStore
    private lateinit var setupContainer: View
    private lateinit var webViewContainer: FrameLayout
    private lateinit var webView: WebView

    private val scanLauncher = registerForActivityResult(ScanContract()) { result ->
        val scanned = result.contents
        if (scanned.isNullOrBlank()) return@registerForActivityResult
        if (!scanned.startsWith("http://") && !scanned.startsWith("https://")) {
            Toast.makeText(this, "That doesn't look like a KOTMate table QR code", Toast.LENGTH_LONG).show()
            return@registerForActivityResult
        }
        confirmAndBind(scanned)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        config = TableConfigStore(this)

        setupContainer = findViewById(R.id.setupContainer)
        webViewContainer = findViewById(R.id.webViewContainer)
        webView = findViewById(R.id.webView)
        findViewById<Button>(R.id.scanButton).setOnClickListener { launchScan() }
        findViewById<ImageButton>(R.id.menuButton).setOnClickListener { showOptionsMenu(it) }

        configureWebView()
        showCurrentState()
    }

    override fun onResume() {
        super.onResume()
        // Re-asserted on every resume, not just once — a staff member or an OS dialog
        // (e.g. an app-switcher gesture) can pop the tablet out of lock task, and an
        // unattended table device should snap back into kiosk mode on its own.
        if (config.tableUrl != null) startKioskLock()
    }

    private fun showCurrentState() {
        val url = config.tableUrl
        if (url == null) {
            setupContainer.visibility = View.VISIBLE
            webViewContainer.visibility = View.GONE
        } else {
            setupContainer.visibility = View.GONE
            webViewContainer.visibility = View.VISIBLE
            webView.loadUrl(url)
        }
    }

    private fun launchScan() {
        val options = ScanOptions()
            .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
            .setPrompt("Scan this table's QR code")
            .setBeepEnabled(true)
            .setOrientationLocked(false)
        scanLauncher.launch(options)
    }

    private fun confirmAndBind(url: String) {
        AlertDialog.Builder(this)
            .setTitle("Bind this tablet to this table?")
            .setMessage(url)
            .setPositiveButton("Yes, use this table") { _, _ ->
                config.tableUrl = url
                showCurrentState()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showOptionsMenu(anchor: View) {
        val menu = PopupMenu(this, anchor)
        menu.menu.add("New customer (reload)")
        menu.menu.add("Re-bind this tablet to a different table")
        menu.setOnMenuItemClickListener { item ->
            when (item.title) {
                "New customer (reload)" -> reloadForNextCustomer()
                "Re-bind this tablet to a different table" -> rebind()
            }
            true
        }
        menu.show()
    }

    /** The primary reset action between parties at this table — deliberately a manual
     * staff tap rather than trying to auto-detect "the bill was just paid" purely by
     * watching the WebView from outside, which the single-page guest app gives no
     * reliable, stable signal for without its own code changes. A long-idle safety-net
     * reload (below) backs this up in case staff forget.
     */
    private fun reloadForNextCustomer() {
        config.tableUrl?.let { webView.loadUrl(it) }
    }

    private fun rebind() {
        stopKioskLockIfActive()
        config.clear()
        showCurrentState()
    }

    private fun configureWebView() {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        webView.webViewClient = object : WebViewClient() {}
        webView.webChromeClient = WebChromeClient()
        // The idle safety net — reloads back to this table's own URL on a long fixed
        // interval regardless of what's on screen, so a tablet that somehow got stuck
        // (a crashed tab, a network blip mid-order) never stays broken for a whole shift
        // just because nobody noticed.
        webView.postDelayed(object : Runnable {
            override fun run() {
                config.tableUrl?.let { webView.loadUrl(it) }
                webView.postDelayed(this, IDLE_SAFETY_RELOAD_MS)
            }
        }, IDLE_SAFETY_RELOAD_MS)
    }

    private fun startKioskLock() {
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_FULLSCREEN
            )
        // Screen Pinning — works without any MDM/device-owner enrollment. Staff (or
        // whoever set the tablet up) unpins the normal Android way (hold Back + Overview)
        // if it ever genuinely needs to leave this app.
        runCatching { startLockTask() }
    }

    private fun stopKioskLockIfActive() {
        runCatching { stopLockTask() }
    }

    private companion object {
        const val IDLE_SAFETY_RELOAD_MS = 45 * 60 * 1000L
    }
}
