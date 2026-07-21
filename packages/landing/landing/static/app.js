// SPDX-License-Identifier: MIT
// Logion landing — ambient sci-fi scene.
//
// Two canvases:
//   #scene       — full-page background (glyph rain, starfield, lightning)
//   #hero-canvas — square stage with particle-formed Zeus silhouette
//
// Plus a hidden #hero-ascii decode intro driven by setInterval over
// LOGION_HERO_FRAMES (kept as the boot sequence and for tooling tests).
//
// Honors prefers-reduced-motion: animation collapses to a static frame.

(function () {
  "use strict";

  var ascii = document.getElementById("hero-ascii");
  var frames = window.LOGION_HERO_FRAMES || [];
  var reduced = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : { matches: false, addEventListener: function () {} };
  // Touch / small-viewport: no pointer parallax (there is no mouse to track
  // and it reads as jitter on mobile), lower scene density, and a 30fps
  // frame budget — phone-class CPUs saturate at the desktop workload.
  var coarse = window.matchMedia
    ? window.matchMedia("(max-width: 768px), (pointer: coarse)")
    : { matches: false, addEventListener: function () {} };
  var lightScheme = window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: light)")
    : { matches: false, addEventListener: function () {} };
  var COARSE_FRAME_INTERVAL = 33; // ms — ~30fps cap on coarse pointers

  // ----- ASCII decode intro (hidden, but real) --------------------------
  if (ascii && frames.length) {
    var f = 0;
    ascii.textContent = frames[0];
    var asciiTick = function () {
      f = (f + 1) % frames.length;
      ascii.textContent = frames[f];
    };
    window.setInterval(asciiTick, reduced.matches ? 4000 : 240);
  }

  // ----- Copy installer command ------------------------------------------
  function copyWithFallback(value) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(value);
    }
    var textArea = document.createElement("textarea");
    textArea.value = value;
    textArea.setAttribute("readonly", "readonly");
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand("copy");
      return Promise.resolve();
    } catch (err) {
      return Promise.reject(err);
    } finally {
      document.body.removeChild(textArea);
    }
  }

  function initCopyButtons() {
    var buttons = document.querySelectorAll("[data-copy-command]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        var button = this;
        var command = button.getAttribute("data-copy-command") || "";
        var statusId = button.getAttribute("aria-describedby");
        var status = statusId ? document.getElementById(statusId) : null;
        copyWithFallback(command).then(
          function () {
            if (status) status.textContent = "Copied to clipboard";
            button.setAttribute("data-copied", "true");
            window.setTimeout(function () {
              if (status) status.textContent = "";
              button.removeAttribute("data-copied");
            }, 2200);
          },
          function () {
            if (status) status.textContent = "Copy failed";
          }
        );
      });
    }
  }

  // ----- Shared utilities -----------------------------------------------
  var DPR = Math.min(window.devicePixelRatio || 1, 2);
  var GREEK = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ";
  var GLYPHS = (GREEK + "0123456789·∙+░▒▓").split("");
  var ACCENT = "#c9a76a";
  var ACCENT_BRIGHT = "#f5d68a";
  var BOLT = "#aed7ff";
  var FG_DIM = "#7d8794";

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function pick(arr) {
    return arr[(Math.random() * arr.length) | 0];
  }

  function fitCanvas(canvas) {
    var rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.floor(rect.width * DPR));
    canvas.height = Math.max(1, Math.floor(rect.height * DPR));
    var ctx = canvas.getContext("2d");
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    return { ctx: ctx, w: rect.width, h: rect.height };
  }

  // Mouse state, normalized to [-0.5..0.5] of viewport.
  var mouse = { x: 0, y: 0, raw: { x: 0, y: 0 } };
  window.addEventListener(
    "mousemove",
    function (e) {
      mouse.raw.x = e.clientX;
      mouse.raw.y = e.clientY;
      mouse.x = e.clientX / window.innerWidth - 0.5;
      mouse.y = e.clientY / window.innerHeight - 0.5;
    },
    { passive: true }
  );

  // ----- Background scene ------------------------------------------------
  var sceneCanvas = document.getElementById("scene");
  var bgState = null;

  function initScene() {
    if (!sceneCanvas) return;
    var dim = fitCanvas(sceneCanvas);
    var w = dim.w;
    var h = dim.h;

    // Glyph columns (Matrix-style rain). Wider spacing on coarse pointers:
    // fewer columns → fewer fillText calls per frame.
    var columnWidth = coarse.matches ? 22 : 14;
    var cols = Math.ceil(w / columnWidth);
    var rain = [];
    for (var i = 0; i < cols; i++) {
      rain.push({
        x: i * columnWidth + 4,
        y: rand(-h, 0),
        speed: rand(80, 220),
        len: (rand(6, 18) | 0),
        glyph: pick(GLYPHS),
        seed: rand(0, 1000),
      });
    }

    // Static-ish starfield.
    var stars = [];
    var density = coarse.matches
      ? Math.min(120, Math.floor((w * h) / 12000))
      : Math.min(260, Math.floor((w * h) / 6000));
    for (var s = 0; s < density; s++) {
      stars.push({
        x: rand(0, w),
        y: rand(0, h),
        r: rand(0.3, 1.4),
        a: rand(0.2, 0.7),
        ph: rand(0, Math.PI * 2),
      });
    }

    bgState = {
      ctx: dim.ctx,
      w: w,
      h: h,
      rain: rain,
      stars: stars,
      bolts: [],
      lastBolt: 0,
    };
  }

  function makeBolt(w, h) {
    // Jagged polyline from top edge toward hero region.
    var startX = rand(w * 0.1, w * 0.9);
    var endX = w * 0.5 + rand(-w * 0.1, w * 0.1);
    var endY = h * 0.55;
    var pts = [{ x: startX, y: 0 }];
    var steps = 14;
    for (var i = 1; i <= steps; i++) {
      var t = i / steps;
      var x = startX + (endX - startX) * t + rand(-22, 22);
      var y = (endY * t) + rand(-6, 6);
      pts.push({ x: x, y: y });
    }
    return { pts: pts, life: 1.0, branches: branchesFrom(pts) };
  }

  function branchesFrom(pts) {
    var branches = [];
    for (var i = 3; i < pts.length - 1; i++) {
      if (Math.random() < 0.22) {
        var base = pts[i];
        var bpts = [base];
        var dx = rand(-1, 1) > 0 ? 1 : -1;
        for (var j = 0; j < 5; j++) {
          bpts.push({
            x: bpts[j].x + dx * rand(6, 18),
            y: bpts[j].y + rand(4, 12),
          });
        }
        branches.push(bpts);
      }
    }
    return branches;
  }

  function drawScene(dt, now) {
    if (!bgState) return;
    var ctx = bgState.ctx;
    var w = bgState.w;
    var h = bgState.h;

    // Trail-clear: light overlay instead of clearRect for ghost trails.
    // Pick a trail colour that matches current theme so light mode does
    // not accumulate a dark wash over the page background. (Cached
    // MediaQueryList — constructing one per frame is measurable overhead.)
    var lightMode = lightScheme.matches;
    // Near-neutral warm gray rain; barely tinted so it stays quiet on
    // both themes and reads as ink/dust rather than gold.
    var rainHead = lightMode ? "95, 92, 86" : "215, 213, 207";
    var rainTail = lightMode ? "135, 132, 126" : "172, 170, 164";
    ctx.fillStyle = lightMode
      ? "rgba(245, 242, 233, 0.32)"
      : "rgba(5, 6, 8, 0.32)";
    ctx.fillRect(0, 0, w, h);

    // Stars.
    ctx.save();
    for (var i = 0; i < bgState.stars.length; i++) {
      var st = bgState.stars[i];
      var twinkle = 0.55 + 0.45 * Math.sin(now * 0.001 + st.ph);
      ctx.globalAlpha = st.a * twinkle;
      ctx.fillStyle = "#dde6f1";
      ctx.fillRect(st.x, st.y, st.r, st.r);
    }
    ctx.restore();

    // Glyph rain.
    ctx.font =
      "12px JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.textBaseline = "top";
    for (var c = 0; c < bgState.rain.length; c++) {
      var col = bgState.rain[c];
      col.y += col.speed * dt;
      if (col.y - col.len * 14 > h) {
        col.y = rand(-200, -20);
        col.speed = rand(80, 220);
        col.glyph = pick(GLYPHS);
      }
      // mouse parallax: nudge column slightly toward cursor X.
      var px = col.x + mouse.x * 6;
      for (var k = 0; k < col.len; k++) {
        var yy = col.y - k * 14;
        if (yy < -14 || yy > h + 14) continue;
        var fade = 1 - k / col.len;
        if (k === 0) {
          ctx.fillStyle = "rgba(" + rainHead + "," + (0.15 * fade) + ")";
        } else {
          ctx.fillStyle = "rgba(" + rainTail + "," + (0.12 * fade) + ")";
        }
        // cycle glyph slowly per cell
        var ch = GLYPHS[
          (((col.seed + k * 7 + (now * 0.001) | 0) % GLYPHS.length) +
            GLYPHS.length) %
            GLYPHS.length
        ];
        ctx.fillText(ch, px, yy);
      }
    }

    // Lightning.
    var elapsed = now - bgState.lastBolt;
    var nextIn = reduced.matches ? 20000 : 5200 + Math.sin(now * 0.0002) * 2000;
    if (elapsed > nextIn) {
      bgState.bolts.push(makeBolt(w, h));
      bgState.lastBolt = now;
    }
    for (var b = bgState.bolts.length - 1; b >= 0; b--) {
      var bolt = bgState.bolts[b];
      bolt.life -= dt * (reduced.matches ? 0.4 : 1.6);
      if (bolt.life <= 0) {
        bgState.bolts.splice(b, 1);
        continue;
      }
      ctx.save();
      ctx.globalAlpha = Math.max(0, bolt.life);
      ctx.strokeStyle = BOLT;
      ctx.lineWidth = 1.6;
      ctx.shadowColor = BOLT;
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.moveTo(bolt.pts[0].x, bolt.pts[0].y);
      for (var p = 1; p < bolt.pts.length; p++) {
        ctx.lineTo(bolt.pts[p].x, bolt.pts[p].y);
      }
      ctx.stroke();
      for (var bi = 0; bi < bolt.branches.length; bi++) {
        var br = bolt.branches[bi];
        ctx.beginPath();
        ctx.moveTo(br[0].x, br[0].y);
        for (var bp = 1; bp < br.length; bp++) {
          ctx.lineTo(br[bp].x, br[bp].y);
        }
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  // ----- Hero canvas (Zeus particle figure) ------------------------------
  var heroCanvas = document.getElementById("hero-canvas");
  var heroState = null;
  // Skip hero drawing entirely once the hero scrolls out of view — the
  // particles are the most expensive draw and invisible while reading.
  var heroVisible = true;
  if (heroCanvas && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      heroVisible = entries[entries.length - 1].isIntersecting;
    }).observe(heroCanvas);
  }

  function silhouette(x, y, w, h) {
    var cx = w / 2;
    var nx = (x - cx) / (w * 0.5);
    var ny = y / h;
    // Head: ellipse centered ~y=0.34
    var head = Math.pow(nx / 0.42, 2) +
               Math.pow((ny - 0.34) / 0.22, 2) < 1;
    // Laurel/hair flourish on top
    var hair = Math.pow(nx / 0.5, 2) +
               Math.pow((ny - 0.18) / 0.08, 2) < 1;
    // Beard: triangle widening downward from ~y=0.5 to 0.78
    var beard = ny > 0.5 && ny < 0.78 &&
                Math.abs(nx) < (0.78 - ny) * 1.6 + 0.04;
    // Shoulders trapezoid
    var shoulders = ny > 0.74 && ny < 0.95 &&
                    Math.abs(nx) < 0.42 + (ny - 0.74) * 1.4;
    // Robe (chest)
    var robe = ny > 0.82 && ny < 1.05 &&
               Math.abs(nx) < 0.55;
    return head || hair || beard || shoulders || robe;
  }

  function initHero() {
    if (!heroCanvas) return;
    var dim = fitCanvas(heroCanvas);
    var w = dim.w;
    var h = dim.h;

    // Sample particle home positions over the silhouette. Coarser sampling
    // on coarse pointers: ~half the particles, same figure.
    var particles = [];
    var step = coarse.matches ? 9 : 6;
    var driftChance = coarse.matches ? 0 : 0.012;
    for (var y = 0; y < h; y += step) {
      for (var x = 0; x < w; x += step) {
        if (silhouette(x, y, w, h)) {
          if (Math.random() < 0.62) {
            particles.push({
              hx: x + rand(-1.4, 1.4),
              hy: y + rand(-1.4, 1.4),
              x: x + rand(-w, w),
              y: y + rand(-h, h),
              phase: rand(0, Math.PI * 2),
              glyph: Math.random() < 0.5 ? pick(GLYPHS) : "·",
              size: rand(8, 13),
              edge: edgeWeight(x, y, w, h),
            });
          }
        } else if (Math.random() < driftChance) {
          // sparse drift particles outside silhouette
          particles.push({
            hx: x,
            hy: y,
            x: x,
            y: y,
            phase: rand(0, Math.PI * 2),
            glyph: "·",
            size: 8,
            edge: 0,
            drift: true,
          });
        }
      }
    }

    heroState = {
      ctx: dim.ctx,
      w: w,
      h: h,
      particles: particles,
      t0: performance.now(),
      bolts: [],
      lastBolt: 0,
    };
  }

  function edgeWeight(x, y, w, h) {
    // approximate distance to silhouette edge by sampling neighbors
    var miss = 0;
    var r = 8;
    for (var i = 0; i < 8; i++) {
      var a = (i / 8) * Math.PI * 2;
      if (!silhouette(x + Math.cos(a) * r, y + Math.sin(a) * r, w, h)) {
        miss++;
      }
    }
    return miss / 8; // 0 = deep interior, 1 = strong edge
  }

  function drawHero(dt, now) {
    if (!heroState || !heroVisible) return;
    var ctx = heroState.ctx;
    var w = heroState.w;
    var h = heroState.h;
    var t = (now - heroState.t0) / 1000;

    ctx.clearRect(0, 0, w, h);

    // Parallax offset.
    var px = mouse.x * 14;
    var py = mouse.y * 10;

    // Breathing scale.
    var breathe = 1 + Math.sin(t * 0.8) * 0.012;

    ctx.font =
      "11px JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";

    var parts = heroState.particles;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      // ease toward home position
      var targetX = ((p.hx - w / 2) * breathe) + w / 2 + px;
      var targetY = ((p.hy - h / 2) * breathe) + h / 2 + py;
      // jitter
      var jx = Math.sin(t * 1.3 + p.phase) * (1.2 + p.edge * 2.2);
      var jy = Math.cos(t * 1.1 + p.phase * 1.3) * (1.2 + p.edge * 2.2);
      p.x += (targetX + jx - p.x) * Math.min(1, dt * (reduced.matches ? 12 : 5));
      p.y += (targetY + jy - p.y) * Math.min(1, dt * (reduced.matches ? 12 : 5));

      // colour: edge → bright accent, interior → dimmer
      var alpha = 0.35 + 0.55 * p.edge;
      if (p.drift) {
        ctx.fillStyle = "rgba(125, 135, 148, 0.22)";
      } else if (p.edge > 0.45) {
        ctx.fillStyle = "rgba(245, 214, 138," + alpha + ")";
      } else {
        ctx.fillStyle = "rgba(201, 167, 106," + (alpha * 0.7) + ")";
      }

      // occasionally cycle glyph
      if (!p.drift && (((i + (t * 4) | 0) % 137) === 0)) {
        p.glyph = pick(GLYPHS);
      }

      ctx.fillText(p.glyph, p.x, p.y);
    }

    // Inner lightning sparks around the figure (rare).
    var sinceBolt = now - heroState.lastBolt;
    var boltGap = reduced.matches ? 14000 : 3400;
    if (sinceBolt > boltGap) {
      var startX = rand(w * 0.15, w * 0.85);
      var startY = rand(0, h * 0.2);
      var pts = [{ x: startX, y: startY }];
      var tx = w / 2 + px;
      var ty = h * 0.45 + py;
      for (var s = 1; s <= 8; s++) {
        var tt = s / 8;
        pts.push({
          x: startX + (tx - startX) * tt + rand(-10, 10),
          y: startY + (ty - startY) * tt + rand(-4, 4),
        });
      }
      heroState.bolts.push({ pts: pts, life: 1 });
      heroState.lastBolt = now;
    }
    for (var b = heroState.bolts.length - 1; b >= 0; b--) {
      var bolt = heroState.bolts[b];
      bolt.life -= dt * 2.2;
      if (bolt.life <= 0) {
        heroState.bolts.splice(b, 1);
        continue;
      }
      ctx.save();
      ctx.globalAlpha = Math.max(0, bolt.life);
      ctx.strokeStyle = BOLT;
      ctx.lineWidth = 1.4;
      ctx.shadowColor = BOLT;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(bolt.pts[0].x, bolt.pts[0].y);
      for (var pi = 1; pi < bolt.pts.length; pi++) {
        ctx.lineTo(bolt.pts[pi].x, bolt.pts[pi].y);
      }
      ctx.stroke();
      ctx.restore();
    }
  }

  // ----- Loop & lifecycle -----------------------------------------------
  var last = performance.now();
  var frameHandle = 0;
  var running = false;
  var frameCount = 0;
  var lastLogged = 0;
  var LOG = function () {
    try {
      var args = ["[logion]"].concat(Array.prototype.slice.call(arguments));
      console.log.apply(console, args);
    } catch (e) {}
  };

  function frame(now) {
    if (!running) {
      LOG("frame fired but running=false, exiting", { now: now });
      return;
    }
    // 30fps budget on coarse pointers: skip the draw, keep the loop alive.
    if (coarse.matches && now - last < COARSE_FRAME_INTERVAL) {
      frameHandle = window.requestAnimationFrame(frame);
      return;
    }
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    frameCount++;
    if (now - lastLogged > 2000) {
      LOG("frame tick", {
        now: now,
        dt: dt,
        frames: frameCount,
        hidden: document.hidden,
        running: running,
        frameHandle: frameHandle,
        bgBolts: bgState ? bgState.bolts.length : null,
        heroBolts: heroState ? heroState.bolts.length : null,
        heroParticles: heroState ? heroState.particles.length : null,
      });
      lastLogged = now;
    }
    drawScene(dt, now);
    drawHero(dt, now);
    updateSilhouetteParallax(dt);
    frameHandle = window.requestAnimationFrame(frame);
  }

  // ----- Zeus backdrop parallax --------------------------------------
  // The backdrop is a raster <img>, so the eased pointer parallax is a
  // cheap compositor transform. Still: never on coarse/reduced (the
  // target is 0 there), and skip the write when the eased value hasn't
  // changed.
  var silEl = null;
  var silParX = 0;
  var silParY = 0;
  var silLastTransform = "";
  function updateSilhouetteParallax(dt) {
    if (reduced.matches || coarse.matches) return;
    if (!silEl) silEl = document.getElementById("silhouette");
    if (!silEl) return;
    var k = Math.min(1, dt * 3.5);
    silParX += (-mouse.x * 36 - silParX) * k;
    // Vertical target clamped to >= 0: the figure is flush with the
    // viewport bottom, so it may dip below the edge but never lift off it.
    silParY += (Math.max(0, -mouse.y * 22) - silParY) * k;
    var next =
      "translate(" + silParX.toFixed(2) + "px, " + silParY.toFixed(2) + "px)";
    if (next === silLastTransform) return;
    silLastTransform = next;
    silEl.style.transform = next;
  }

  // Reduced motion: no animation loop at all — one composed frame, done.
  // (This is what the header comment always promised; previously the rAF
  // loop kept running at full rate with slower parameters.)
  function renderStaticFrame() {
    var now = performance.now();
    if (heroState) {
      var parts = heroState.particles;
      for (var i = 0; i < parts.length; i++) {
        parts[i].x = parts[i].hx;
        parts[i].y = parts[i].hy;
      }
    }
    drawScene(0.016, now);
    drawHero(0.016, now);
  }

  function startLoop() {
    LOG("startLoop called", { running: running, hidden: document.hidden, frameHandle: frameHandle });
    if (reduced.matches) {
      LOG("startLoop: reduced motion, rendering static frame");
      renderStaticFrame();
      return;
    }
    if (running) {
      LOG("startLoop: already running, no-op");
      return;
    }
    running = true;
    last = performance.now();
    frameHandle = window.requestAnimationFrame(frame);
    LOG("startLoop: queued rAF", { frameHandle: frameHandle, last: last });
  }

  function stopLoop() {
    LOG("stopLoop called", { running: running, frameHandle: frameHandle });
    running = false;
    if (frameHandle) {
      window.cancelAnimationFrame(frameHandle);
      frameHandle = 0;
    }
  }

  // ----- Section stacking ---------------------------------------------
  // Content sections are position: sticky so each pins and the next one
  // slides over it. Short sections pin at the top of the viewport; a
  // section taller than the viewport gets a negative top so it pins only
  // once its bottom has been reached (nothing becomes unreadable).
  var stackBound = false;
  var stackSections = [];

  // As the next section slides up over the pinned one, fade the pinned
  // one out — sections have no background (the ambient scene stays
  // visible), so the fade is what keeps the overlap legible.
  function updateSectionFade() {
    var vh = window.innerHeight;
    for (var i = 0; i < stackSections.length - 1; i++) {
      var rect = stackSections[i].getBoundingClientRect();
      var nextTop = stackSections[i + 1].getBoundingClientRect().top;
      var covered = rect.bottom - nextTop;
      // Accelerated fade: fully gone once ~60% covered, so the two
      // texts never sit legibly on top of each other.
      var span = (Math.min(rect.height, vh) || 1) * 0.6;
      var p = Math.max(0, Math.min(1, covered / span));
      stackSections[i].style.opacity = (1 - p).toFixed(3);
    }
  }

  var fadeQueued = false;
  function queueSectionFade() {
    if (fadeQueued) return;
    fadeQueued = true;
    window.requestAnimationFrame(function () {
      fadeQueued = false;
      updateSectionFade();
    });
  }

  function initSectionStack() {
    stackSections = Array.prototype.slice.call(
      document.querySelectorAll("main > .content-section")
    );
    var vh = window.innerHeight;
    for (var i = 0; i < stackSections.length; i++) {
      var overflow = stackSections[i].offsetHeight - vh;
      stackSections[i].style.top = (overflow > 0 ? -overflow : 0) + "px";
    }
    updateSectionFade();
    if (!stackBound) {
      stackBound = true;
      window.addEventListener("scroll", queueSectionFade, { passive: true });
      // Section heights change after load: FAQ answers expanding and
      // images finishing their fetch both need a recompute.
      var faqs = document.querySelectorAll(".faq-item");
      for (var f = 0; f < faqs.length; f++) {
        faqs[f].addEventListener("toggle", initSectionStack);
      }
      window.addEventListener("load", initSectionStack);
    }
  }

  // ----- Smooth wheel scrolling -----------------------------------------
  // CSS scroll-behavior only smooths anchor/programmatic scrolls; wheel
  // input stays native. This eases wheel deltas toward a target with a
  // rAF lerp for the buttery feel. Deliberately NOT active for: coarse
  // pointers (touch scrolling is already smooth and must stay native),
  // reduced motion, and ctrl+wheel (browser zoom).
  function initSmoothWheel() {
    if (reduced.matches || coarse.matches) return;
    var targetY = window.scrollY;
    var currentY = targetY;
    var animating = false;

    function maxScroll() {
      return Math.max(
        0,
        document.documentElement.scrollHeight - window.innerHeight
      );
    }

    function tick() {
      currentY += (targetY - currentY) * 0.14;
      if (Math.abs(targetY - currentY) < 0.6) {
        currentY = targetY;
        animating = false;
      }
      // behavior: "instant" bypasses the CSS smooth behavior — without it
      // every tick would itself be smoothed and the scroll would lag.
      window.scrollTo({ top: currentY, behavior: "instant" });
      if (animating) window.requestAnimationFrame(tick);
    }

    window.addEventListener(
      "wheel",
      function (e) {
        // Terminal transcripts are independent scroll regions. Let the
        // browser handle wheel input there instead of moving the page.
        if (
          e.target instanceof Element &&
          e.target.closest(".hero-demo__body")
        ) {
          return;
        }
        if (e.ctrlKey || e.defaultPrevented) return;
        e.preventDefault();
        var delta = e.deltaY;
        if (e.deltaMode === 1) delta *= 16; // line mode → px
        targetY = Math.max(0, Math.min(maxScroll(), targetY + delta));
        if (!animating) {
          animating = true;
          window.requestAnimationFrame(tick);
        }
      },
      { passive: false }
    );

    // Keyboard, scrollbar drags, and anchor jumps move the page without
    // us — resync so the next wheel tick starts from reality.
    window.addEventListener(
      "scroll",
      function () {
        if (!animating) {
          targetY = window.scrollY;
          currentY = targetY;
        }
      },
      { passive: true }
    );
  }

  function start() {
    initCopyButtons();
    initScene();
    initHero();
    initSectionStack();
    initSmoothWheel();
    if (!document.hidden) {
      startLoop();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

  // Refit on resize.
  var resizeHandle = null;
  window.addEventListener("resize", function () {
    if (resizeHandle) window.clearTimeout(resizeHandle);
    resizeHandle = window.setTimeout(function () {
      initScene();
      initHero();
      initSectionStack();
    }, 160);
  });

  // React to reduced-motion changes.
  if (reduced.addEventListener) {
    reduced.addEventListener("change", function () {
      // re-init so steady-state honors new preference, then either resume
      // the loop or settle on a fresh static frame.
      stopLoop();
      initScene();
      initHero();
      if (!document.hidden) {
        startLoop();
      }
    });
  }

  document.addEventListener("visibilitychange", function () {
    LOG("visibilitychange", {
      hidden: document.hidden,
      visibilityState: document.visibilityState,
      running: running,
      frameHandle: frameHandle,
    });
    if (document.hidden) {
      stopLoop();
    } else {
      startLoop();
    }
  });

  window.addEventListener("pageshow", function (e) {
    LOG("pageshow", { persisted: e.persisted, hidden: document.hidden, running: running });
    startLoop();
  });

  window.addEventListener("pagehide", function (e) {
    LOG("pagehide", { persisted: e.persisted });
    stopLoop();
  });

  window.addEventListener("freeze", function () {
    LOG("freeze event fired");
  });

  window.addEventListener("resume", function () {
    LOG("resume event fired");
  });

  LOG("app.js loaded", {
    readyState: document.readyState,
    hidden: document.hidden,
    visibilityState: document.visibilityState,
  });
})();
