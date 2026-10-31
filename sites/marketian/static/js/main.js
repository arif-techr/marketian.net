(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.add("js");

  // Theme toggle
  var themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  // Mobile navigation
  var navBtn = document.getElementById("nav-toggle");
  if (navBtn) {
    navBtn.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      navBtn.setAttribute("aria-expanded", String(open));
      navBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && document.body.classList.contains("nav-open")) navBtn.click();
    });
  }

  // Header border once scrolled
  var header = document.querySelector(".site-header");
  var onScroll = function () { header && header.classList.toggle("is-scrolled", window.scrollY > 8); };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Marketian / Marketain switcher: rotates on its own until the visitor picks one
  var hero = document.querySelector(".hero[data-identity]");
  if (hero) {
    var options = hero.querySelectorAll("[data-identity-target]");
    var show = function (id) {
      hero.setAttribute("data-identity", id);
      options.forEach(function (btn) {
        btn.setAttribute("aria-pressed", String(btn.getAttribute("data-identity-target") === id));
      });
    };
    var timer = null;
    var paused = false;
    var stop = function () { clearInterval(timer); timer = null; };
    options.forEach(function (btn) {
      btn.addEventListener("click", function () { stop(); show(btn.getAttribute("data-identity-target")); });
    });
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      var box = hero.querySelector(".identity");
      ["mouseenter", "focusin"].forEach(function (ev) { box.addEventListener(ev, function () { paused = true; }); });
      ["mouseleave", "focusout"].forEach(function (ev) { box.addEventListener(ev, function () { paused = false; }); });
      timer = setInterval(function () {
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
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var targets = document.querySelectorAll(".reveal, [data-count]");
  if (!("IntersectionObserver" in window) || reduced) {
    targets.forEach(function (el) { el.classList.add("is-visible"); });
    return;
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      if (entry.target.hasAttribute("data-count")) countUp(entry.target);
      io.unobserve(entry.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  targets.forEach(function (el) { io.observe(el); });
})();
