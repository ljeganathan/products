// Loads GA4 / Meta Pixel only if an ID is configured (js/analytics-config.js),
// and exposes window.kotmateTrack(event, params) used by main.js for the
// event set the landing-page brief asks for: page_view, pricing_view,
// start_trial_click, login_click, demo_click, whatsapp_click, contact_click.
(function () {
  var cfg = window.KOTMATE_ANALYTICS_CONFIG || {};
  var hasGA = !!cfg.ga4MeasurementId;
  var hasPixel = !!cfg.metaPixelId;

  if (hasGA) {
    var gaScript = document.createElement("script");
    gaScript.async = true;
    gaScript.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(cfg.ga4MeasurementId);
    document.head.appendChild(gaScript);

    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    gtag("js", new Date());
    gtag("config", cfg.ga4MeasurementId);

    if (cfg.googleAdsConversion && cfg.googleAdsConversion.id) {
      gtag("config", cfg.googleAdsConversion.id);
    }
  }

  if (hasPixel) {
    /* eslint-disable */
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
    n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
    document,'script','https://connect.facebook.net/en_US/fbevents.js');
    /* eslint-enable */
    fbq("init", cfg.metaPixelId);
    fbq("track", "PageView");
  }

  // A no-op fallback keeps main.js's call sites simple even with zero
  // analytics configured (e.g. during local dev).
  window.kotmateTrack = function (eventName, params) {
    params = params || {};
    if (hasGA && window.gtag) {
      gtag("event", eventName, params);
      if (
        (eventName === "start_trial_click" || eventName === "demo_click") &&
        cfg.googleAdsConversion &&
        cfg.googleAdsConversion.id &&
        cfg.googleAdsConversion.label
      ) {
        gtag("event", "conversion", {
          send_to: cfg.googleAdsConversion.id + "/" + cfg.googleAdsConversion.label,
        });
      }
    }
    if (hasPixel && window.fbq) {
      var metaEventMap = {
        start_trial_click: "StartTrial",
        demo_click: "Contact",
        login_click: "Login",
        whatsapp_click: "Contact",
        contact_click: "Contact",
        pricing_view: "ViewContent",
      };
      fbq("trackCustom", metaEventMap[eventName] || eventName, params);
    }
  };
})();
