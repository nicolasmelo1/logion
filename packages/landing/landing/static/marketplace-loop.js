// SPDX-License-Identifier: MIT
// Scroll-reveal and the marketplace cycle orbit animation.
(function () {
  "use strict";

  // --- Scroll reveal -------------------------------------------------------
  var revealEls = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    revealEls.forEach(function (el) {
      el.classList.add("in");
    });
  } else {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
    );
    revealEls.forEach(function (el) {
      io.observe(el);
    });
  }

  // --- Marketplace cycle orbit ---------------------------------------------
  var canvas = document.getElementById("cycleCanvas");
  if (!canvas) {
    return;
  }
  var ctx = canvas.getContext("2d");
  var reduce =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var W = 0;
  var H = 0;
  var cx = 0;
  var cy = 0;
  var R = 0;

  function size() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var rect = canvas.getBoundingClientRect();
    W = rect.width;
    H = rect.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx = W / 2;
    cy = H / 2;
    R = Math.min(W, H) * 0.4;
  }
  size();
  window.addEventListener("resize", size);

  var nodes = [-Math.PI / 2, 0, Math.PI / 2, Math.PI];

  function drawBase() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(201,167,106,0.10)";
    ctx.lineWidth = 1;
    for (var i = 0; i < nodes.length; i++) {
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(nodes[i]) * R, cy + Math.sin(nodes[i]) * R);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(201,167,106,0.34)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    for (var j = 0; j < nodes.length; j++) {
      var nx = cx + Math.cos(nodes[j]) * R;
      var ny = cy + Math.sin(nodes[j]) * R;
      ctx.beginPath();
      ctx.arc(nx, ny, 3, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(201,167,106,0.55)";
      ctx.fill();
    }
  }

  function drawPulse(angle) {
    var px = cx + Math.cos(angle) * R;
    var py = cy + Math.sin(angle) * R;
    ctx.save();
    ctx.shadowColor = "rgba(245,214,138,0.9)";
    ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.arc(px, py, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = "#f0c460";
    ctx.fill();
    ctx.restore();
  }

  if (reduce) {
    drawBase();
    drawPulse(-Math.PI / 2);
    return;
  }

  var t = 0;
  var raf = null;
  var running = false;

  function frame() {
    drawBase();
    for (var k = 0; k < 3; k++) {
      drawPulse(t + (k * 2 * Math.PI) / 3);
    }
    t += 0.012;
    raf = requestAnimationFrame(frame);
  }

  function startLoop() {
    if (!running) {
      running = true;
      raf = requestAnimationFrame(frame);
    }
  }

  function stopLoop() {
    running = false;
    if (raf) {
      cancelAnimationFrame(raf);
      raf = null;
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      stopLoop();
    } else {
      startLoop();
    }
  });

  startLoop();
})();
