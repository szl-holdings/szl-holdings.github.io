/* SZL Apex Responsive Experience v3 — local progressive enhancement only. */
(function () {
  "use strict";

  if (window.__SZL_APEX_RESPONSIVE_V3__) return;
  window.__SZL_APEX_RESPONSIVE_V3__ = true;

  var root = document.documentElement;
  var media = {
    compact: window.matchMedia("(max-width: 47.999rem)"),
    theatre: window.matchMedia("(min-width: 100rem)"),
    ultrawide: window.matchMedia("(min-width: 150rem)"),
    coarse: window.matchMedia("(pointer: coarse)"),
    reduce: window.matchMedia("(prefers-reduced-motion: reduce)"),
    contrast: window.matchMedia("(prefers-contrast: more)"),
  };

  function viewportClass() {
    if (media.ultrawide.matches) return "ultrawide";
    if (media.theatre.matches) return "theatre";
    if (media.compact.matches) return "compact";
    return "standard";
  }

  function applyEnvironment() {
    root.dataset.szlViewport = viewportClass();
    root.dataset.szlInput = media.coarse.matches ? "coarse" : "fine";
    root.dataset.szlMotion = media.reduce.matches ? "quiet" : "dynamic";
    root.dataset.szlContrast = media.contrast.matches ? "increased" : "standard";
    root.style.setProperty("--apex-visual-height", Math.round(window.visualViewport ? window.visualViewport.height : window.innerHeight) + "px");
  }

  function updateProgress() {
    var total = Math.max(1, root.scrollHeight - window.innerHeight);
    var progress = Math.max(0, Math.min(100, (window.scrollY / total) * 100));
    root.style.setProperty("--apex-progress", progress.toFixed(2) + "%");
  }

  var frame = 0;
  function schedule() {
    if (frame) return;
    frame = window.requestAnimationFrame(function () {
      frame = 0;
      applyEnvironment();
      updateProgress();
    });
  }

  Object.keys(media).forEach(function (key) {
    var query = media[key];
    if (typeof query.addEventListener === "function") query.addEventListener("change", schedule);
    else if (typeof query.addListener === "function") query.addListener(schedule);
  });

  window.addEventListener("resize", schedule, { passive: true });
  window.addEventListener("orientationchange", schedule, { passive: true });
  window.addEventListener("scroll", schedule, { passive: true });
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", schedule, { passive: true });
    window.visualViewport.addEventListener("scroll", schedule, { passive: true });
  }

  if (!media.reduce.matches && !media.coarse.matches) {
    window.addEventListener("pointermove", function (event) {
      root.style.setProperty("--apex-pointer-x", ((event.clientX / Math.max(1, window.innerWidth)) * 100).toFixed(2) + "%");
      root.style.setProperty("--apex-pointer-y", ((event.clientY / Math.max(1, window.innerHeight)) * 100).toFixed(2) + "%");
    }, { passive: true });
  }

  document.addEventListener("visibilitychange", function () {
    root.dataset.szlVisibility = document.hidden ? "hidden" : "visible";
    if (!document.hidden) schedule();
  });

  applyEnvironment();
  updateProgress();
}());
