package com.kotmatetn.tableorder

import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
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
            webView.loadUrl(fixedDeviceUrl(url))
        }
    }

    /** This tablet is bolted to the table, never a customer's own phone — the guest
     * ordering page has no other way to tell the two apart, and without this it would
     * show "Open Google Pay/PhonePe" buttons that launch those apps on the restaurant's
     * own fixed device instead of a customer's (production feedback). Appends rather
     * than assumes a bare URL, since a re-scanned/edited table QR could already carry
     * its own query string.
     */
    private fun fixedDeviceUrl(rawUrl: String): String =
        rawUrl + (if (rawUrl.contains("?")) "&" else "?") + "fixed_device=1"

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
        config.tableUrl?.let { webView.loadUrl(fixedDeviceUrl(it)) }
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
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                handleExternalAppLaunch(view, request.url.toString())
        }
        webView.webChromeClient = WebChromeClient()
        // The idle safety net — reloads back to this table's own URL on a long fixed
        // interval regardless of what's on screen, so a tablet that somehow got stuck
        // (a crashed tab, a network blip mid-order) never stays broken for a whole shift
        // just because nobody noticed.
        webView.postDelayed(object : Runnable {
            override fun run() {
                config.tableUrl?.let { webView.loadUrl(fixedDeviceUrl(it)) }
                webView.postDelayed(this, IDLE_SAFETY_RELOAD_MS)
            }
        }, IDLE_SAFETY_RELOAD_MS)
    }

    /** A plain WebView has no built-in way to hand off to an installed app the way a real
     * browser (Chrome) does — so without this, tapping "Google Pay"/"PhonePe" inside the
     * Razorpay/Cashfree checkout silently does nothing, even though the exact same page
     * works fine in an ordinary mobile browser tab. `intent://...#Intent;...;end` (and a
     * bare custom scheme like `upi://pay?...`) are both parsed the same way UPI payment
     * SDKs expect a WebView host to handle them. Returns true (navigation handled here)
     * for anything that isn't a plain http(s) page load.
     */
    private fun handleExternalAppLaunch(view: WebView, url: String): Boolean {
        if (url.startsWith("http://") || url.startsWith("https://")) return false
        return try {
            val intent = Intent.parseUri(url, Intent.URI_INTENT_SCHEME)
            intent.addCategory(Intent.CATEGORY_BROWSABLE)
            intent.component = null
            intent.selector = null
            if (intent.resolveActivity(packageManager) != null) {
                startActivity(intent)
            } else {
                // No app installed for this UPI intent — most of these carry a fallback
                // page (e.g. "install this app" or a plain web payment option) under this
                // well-known extra key; load it if present instead of just doing nothing.
                intent.getStringExtra("browser_fallback_url")?.let { view.loadUrl(it) }
            }
            true
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(this, "That app isn't installed on this device", Toast.LENGTH_SHORT).show()
            true
        } catch (e: Exception) {
            false
        }
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
