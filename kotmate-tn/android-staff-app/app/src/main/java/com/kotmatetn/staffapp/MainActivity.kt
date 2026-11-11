package com.kotmatetn.staffapp

import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.switchmaterial.SwitchMaterial
import com.google.android.material.textfield.TextInputEditText

/** One generic screen for any staff-operated device — POS terminal, Kitchen Display,
 * or Kiosk. Deliberately dumb: it just loads the configured server URL and gets out of
 * the way. Every role difference (POS vs KOT vs Kiosk, which branch/section, what the
 * logged-in user can see) is already handled by KOTMate's own login and routing — this
 * app has no idea which role is using it, and doesn't need to.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var config: AppConfigStore
    private lateinit var webView: WebView
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var errorContainer: View
    private lateinit var errorDetail: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        config = AppConfigStore(this)

        webView = findViewById(R.id.webView)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        errorContainer = findViewById(R.id.errorContainer)
        errorDetail = findViewById(R.id.errorDetail)

        configureWebView()
        swipeRefresh.setOnRefreshListener { webView.reload() }
        findViewById<Button>(R.id.retryButton).setOnClickListener { loadConfiguredUrl() }
        findViewById<ImageButton>(R.id.menuButton).setOnClickListener { showSettingsDialog() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })

        loadConfiguredUrl()
    }

    override fun onResume() {
        super.onResume()
        if (config.kioskLockEnabled) startKioskLock()
    }

    private fun configureWebView() {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                swipeRefresh.isRefreshing = false
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?,
            ) {
                super.onReceivedError(view, request, error)
                // Only the main page failing counts as "can't reach KOTMate" — a failed
                // sub-resource (an analytics script, a font) shouldn't blank the screen.
                if (request?.isForMainFrame == true) showError(error?.description?.toString())
            }
        }
    }

    private fun loadConfiguredUrl() {
        errorContainer.visibility = View.GONE
        swipeRefresh.visibility = View.VISIBLE
        webView.loadUrl(config.serverUrl)
    }

    private fun showError(detail: String?) {
        swipeRefresh.isRefreshing = false
        swipeRefresh.visibility = View.GONE
        errorContainer.visibility = View.VISIBLE
        errorDetail.text = detail?.let { "Check the network connection, then try again.\n($it)" }
            ?: "Check the network connection, then try again."
    }

    private fun showSettingsDialog() {
        val view = layoutInflater.inflate(R.layout.dialog_settings, null)
        val urlField = view.findViewById<TextInputEditText>(R.id.urlField)
        val lockSwitch = view.findViewById<SwitchMaterial>(R.id.kioskLockSwitch)
        urlField.setText(config.serverUrl)
        lockSwitch.isChecked = config.kioskLockEnabled

        AlertDialog.Builder(this)
            .setTitle("KOTMate settings")
            .setView(view)
            .setPositiveButton("Save") { _, _ ->
                val newUrl = urlField.text?.toString()?.trim().orEmpty()
                val urlChanged = newUrl.isNotEmpty() && newUrl != config.serverUrl
                if (newUrl.isNotEmpty()) config.serverUrl = newUrl
                val lockWasOn = config.kioskLockEnabled
                config.kioskLockEnabled = lockSwitch.isChecked
                if (lockWasOn && !lockSwitch.isChecked) stopKioskLockIfActive()
                if (urlChanged) loadConfiguredUrl()
            }
            .setNegativeButton("Cancel", null)
            .show()
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
        // Screen Pinning — no MDM/device-owner enrollment needed. Whoever set the
        // terminal up unlocks it the normal Android way (hold Back + Overview).
        runCatching { startLockTask() }
    }

    private fun stopKioskLockIfActive() {
        runCatching { stopLockTask() }
    }
}
