(function () {
  "use strict";

  // "Copy" buttons: <button data-copy="text">.
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn || !navigator.clipboard) return;
    navigator.clipboard.writeText(btn.getAttribute("data-copy")).then(function () {
      var label = btn.textContent;
      btn.textContent = "Copied";
      btn.classList.add("done");
      setTimeout(function () { btn.textContent = label; btn.classList.remove("done"); }, 1500);
    });
  });

  // Pages load without a full reload: htmx (hx-boost on <body>) fetches the next
  // page in the background and swaps it in. This file adds the finishing touches.
  if (!window.htmx) return;
  var root = document.documentElement;

  // Thin progress bar for page changes that take a moment (see .is-loading in CSS).
  document.addEventListener("htmx:beforeSend", function (e) {
    if (e.detail.boosted) root.classList.add("is-loading");
  });
  ["htmx:afterRequest", "htmx:afterSettle", "htmx:sendError", "htmx:timeout"].forEach(function (name) {
    document.addEventListener(name, function () { root.classList.remove("is-loading"); });
  });

  // Start fetching a page when the pointer rests on its link; the server lets the
  // browser keep that copy for a few seconds (dashboard/middleware.py),
  // so the click opens it straight away.
  var prefetched = {};
  var hoverTimer = null;
  function prefetch(link) {
    if (!link || link.hasAttribute("download") || (link.target && link.target !== "_self")) return;
    if (link.origin !== location.origin || link.closest('[hx-boost="false"]')) return;
    if (link.pathname === location.pathname && link.search === location.search) return;
    if (prefetched[link.href] && Date.now() - prefetched[link.href] < 9000) return;
    prefetched[link.href] = Date.now();
    fetch(link.href, { headers: { "HX-Preloaded": "true" }, credentials: "same-origin" }).catch(function () {});
  }
  document.addEventListener("mouseover", function (e) {
    var link = e.target.closest("a[href]");
    clearTimeout(hoverTimer);
    if (link) hoverTimer = setTimeout(function () { prefetch(link); }, 65);
  });
  document.addEventListener("touchstart", function (e) { prefetch(e.target.closest("a[href]")); }, { passive: true });

  // Network trouble on a link: fall back to a normal page load.
  document.addEventListener("htmx:sendError", function (e) {
    var info = e.detail.requestConfig;
    if (e.detail.boosted && info && info.verb === "get") window.location.href = e.detail.pathInfo.requestPath;
  });
})();
