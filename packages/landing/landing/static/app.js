// SPDX-License-Identifier: MIT
// Lightweight ASCII frame swapper for the hero. No canvas, no 3D.
(function () {
  "use strict";

  var target = document.getElementById("hero-ascii");
  var frames = window.LOGION_HERO_FRAMES;
  if (!target || !frames || !frames.length) {
    return;
  }

  var reduced = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

  function intervalMs() {
    return reduced && reduced.matches ? 4000 : 600;
  }

  var i = 0;
  target.textContent = frames[i];

  function tick() {
    i = (i + 1) % frames.length;
    target.textContent = frames[i];
  }

  var handle = window.setInterval(tick, intervalMs());

  if (reduced && typeof reduced.addEventListener === "function") {
    reduced.addEventListener("change", function () {
      window.clearInterval(handle);
      if (reduced.matches) {
        // hold a single frame under reduced motion
        target.textContent = frames[0];
      }
      handle = window.setInterval(tick, intervalMs());
    });
  }
})();
