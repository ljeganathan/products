(function () {
  "use strict";

  var track = function (name, params) {
    if (window.kotmateTrack) window.kotmateTrack(name, params);
  };

  // ---------- Sticky header shadow ----------
  var header = document.querySelector(".site-header");
  if (header) {
    var onScroll = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // ---------- Mobile nav ----------
  var navToggle = document.querySelector(".nav-toggle");
  var mobileNav = document.querySelector(".mobile-nav");
  if (navToggle && mobileNav) {
    navToggle.addEventListener("click", function () {
      var isOpen = mobileNav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
    mobileNav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        mobileNav.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // ---------- FAQ accordion ----------
  document.querySelectorAll(".faq-item").forEach(function (item) {
    var btn = item.querySelector(".faq-item__q");
    var panel = item.querySelector(".faq-item__a");
    btn.addEventListener("click", function () {
      var isOpen = item.getAttribute("data-open") === "true";
      // Close any other open item for a cleaner single-open accordion.
      document.querySelectorAll('.faq-item[data-open="true"]').forEach(function (other) {
        if (other !== item) {
          other.setAttribute("data-open", "false");
          other.querySelector(".faq-item__q").setAttribute("aria-expanded", "false");
          other.querySelector(".faq-item__a").style.maxHeight = null;
        }
      });
      item.setAttribute("data-open", isOpen ? "false" : "true");
      btn.setAttribute("aria-expanded", isOpen ? "false" : "true");
      panel.style.maxHeight = isOpen ? null : panel.scrollHeight + "px";
    });
  });

  // ---------- Screenshot showcase tabs ----------
  var tabs = document.querySelectorAll(".showcase-tab");
  var panels = document.querySelectorAll(".showcase-panel");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var target = tab.getAttribute("data-target");
      tabs.forEach(function (t) { t.setAttribute("aria-selected", t === tab ? "true" : "false"); });
      panels.forEach(function (p) { p.classList.toggle("is-active", p.id === target); });
    });
  });

  // ---------- pricing_view (fires once, first time pricing enters view) ----------
  var pricingSection = document.getElementById("pricing");
  if (pricingSection && "IntersectionObserver" in window) {
    var fired = false;
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !fired) {
            fired = true;
            track("pricing_view");
            io.disconnect();
          }
        });
      },
      { threshold: 0.4 }
    );
    io.observe(pricingSection);
  }

  // ---------- CTA click tracking (data-track="event_name" on any link/button) ----------
  document.querySelectorAll("[data-track]").forEach(function (el) {
    el.addEventListener("click", function () {
      track(el.getAttribute("data-track"), { label: el.getAttribute("data-track-label") || el.textContent.trim() });
    });
  });

  // ---------- page_view ----------
  track("page_view", { page_path: window.location.pathname });
})();
