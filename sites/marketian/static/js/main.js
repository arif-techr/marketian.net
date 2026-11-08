(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.add("js");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Pages load without a full reload (htmx swaps the <body>), so listeners that
  // must survive a page change live on document/window, and per-page setup
  // runs again for every new page in initPage().

  // Theme toggle and mobile navigation
  function setNav(open) {
    document.body.classList.toggle("nav-open", open);
    var btn = document.getElementById("nav-toggle");
    if (btn) {
      btn.setAttribute("aria-expanded", String(open));
      btn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }
  }
  document.addEventListener("click", function (e) {
    if (e.target.closest("#theme-toggle")) {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (err) {}
    } else if (e.target.closest("#nav-toggle")) {
      setNav(!document.body.classList.contains("nav-open"));
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && document.body.classList.contains("nav-open")) setNav(false);
  });

  // Header border once scrolled
  function onScroll() {
    var header = document.querySelector(".site-header");
    if (header) header.classList.toggle("is-scrolled", window.scrollY > 8);
  }
  window.addEventListener("scroll", onScroll, { passive: true });

  // Marketian / Marketain switcher: rotates on its own until the visitor picks one
  var heroTimer = null;
  function initHero(hero) {
    clearInterval(heroTimer);
    heroTimer = null;
    var options = hero.querySelectorAll("[data-identity-target]");
    var show = function (id) {
      hero.setAttribute("data-identity", id);
      options.forEach(function (btn) {
        btn.setAttribute("aria-pressed", String(btn.getAttribute("data-identity-target") === id));
      });
    };
    var paused = false;
    var stop = function () { clearInterval(heroTimer); heroTimer = null; };
    options.forEach(function (btn) {
      btn.addEventListener("click", function () { stop(); show(btn.getAttribute("data-identity-target")); });
    });
    if (!reduced) {
      var box = hero.querySelector(".identity");
      ["mouseenter", "focusin"].forEach(function (ev) { box.addEventListener(ev, function () { paused = true; }); });
      ["mouseleave", "focusout"].forEach(function (ev) { box.addEventListener(ev, function () { paused = false; }); });
      heroTimer = setInterval(function () {
        if (!document.body.contains(hero)) return stop();
        if (!paused) show(hero.getAttribute("data-identity") === "ian" ? "ain" : "ian");
      }, 4000);
    }
  }

  // Count-up numbers
  function countUp(el) {
    var target = parseInt(el.getAttribute("data-count"), 10) || 0;
    var start = null;
    var duration = 1400;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // Reveal-on-scroll
  var io = ("IntersectionObserver" in window && !reduced) ? new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      if (entry.target.hasAttribute("data-count")) countUp(entry.target);
      io.unobserve(entry.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }) : null;

  function within(scope, selector) {
    var found = Array.prototype.slice.call(scope.querySelectorAll(selector));
    if (scope.matches(selector)) found.unshift(scope);
    return found;
  }

  // Runs for the first page and for every page (or part of one) swapped in later.
  function initPage(scope) {
    if (!(scope instanceof Element)) return;
    within(scope, ".hero[data-identity]").forEach(initHero);
    within(scope, ".reveal, [data-count]").forEach(function (el) {
      if (el.classList.contains("is-visible")) return;
      if (io) io.observe(el); else el.classList.add("is-visible");
    });
  }

  if (window.htmx) {
    htmx.onLoad(initPage);

    // A new page: close the mobile menu and refresh the header state.
    document.addEventListener("htmx:afterSettle", function () { setNav(false); onScroll(); });
    document.addEventListener("htmx:historyRestore", function () { setNav(false); onScroll(); });

    // Thin progress bar for page changes that take a moment (see .is-loading in CSS).
    document.addEventListener("htmx:beforeSend", function (e) {
      if (e.detail.boosted) root.classList.add("is-loading");
    });
    ["htmx:afterRequest", "htmx:afterSettle", "htmx:sendError", "htmx:timeout"].forEach(function (name) {
      document.addEventListener(name, function () { root.classList.remove("is-loading"); });
    });

    // Start fetching a page when the pointer rests on its link; the server lets the
    // browser keep that copy for a few seconds (core.middleware.PreloadCacheMiddleware),
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
  } else {
    initPage(document.body);
  }
  onScroll();
})();
