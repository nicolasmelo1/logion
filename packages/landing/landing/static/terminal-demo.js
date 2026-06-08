// SPDX-License-Identifier: MIT
// Animated CLI demo for the Logion landing hero.
//
// Each tab autoplays its command (typewriter) followed by its output
// (line-by-line reveal), then pauses and advances to the next tab.
// Honors prefers-reduced-motion by showing the final frame without typing.
// Clicking a tab pauses the auto-cycle and switches immediately.

(function () {
  "use strict";

  const root = document.querySelector("[data-terminal-demo]");
  if (!root) return;

  const tabs = Array.from(root.querySelectorAll(".hero-demo__tab"));
  const panels = Array.from(root.querySelectorAll(".hero-demo__panel"));
  if (!tabs.length || !panels.length) return;

  // Capture full command/output text once; we then render incrementally.
  const frames = panels.map((panel) => {
    const id = panel.dataset.panel;
    const cmdEl = panel.querySelector("[data-cmd]");
    const outEl = panel.querySelector("[data-out]");
    return {
      id,
      panel,
      cmdEl,
      outEl,
      command: cmdEl ? cmdEl.textContent : "",
      output: outEl ? outEl.textContent : "",
    };
  });

  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  // Show only the active panel.
  function setActive(idx) {
    tabs.forEach((tab, i) => {
      const on = i === idx;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach((panel, i) => {
      const on = i === idx;
      panel.classList.toggle("is-active", on);
      panel.setAttribute("aria-hidden", on ? "false" : "true");
    });
  }

  function renderStatic(frame) {
    if (frame.cmdEl) frame.cmdEl.textContent = frame.command;
    if (frame.outEl) frame.outEl.textContent = frame.output;
  }

  function clearFrame(frame) {
    if (frame.cmdEl) frame.cmdEl.textContent = "";
    if (frame.outEl) frame.outEl.textContent = "";
  }

  let aborted = false;
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function typeText(el, text, msPerChar) {
    for (let i = 0; i < text.length; i += 1) {
      if (aborted) return;
      el.textContent += text[i];
      // Slow down briefly at line breaks for rhythm.
      const wait = text[i] === "\n" ? msPerChar * 6 : msPerChar;
      await sleep(wait);
    }
  }

  let currentIndex = 0;
  let runToken = 0;

  async function playFrame(idx) {
    const myToken = ++runToken;
    aborted = false;
    setActive(idx);
    const frame = frames[idx];
    clearFrame(frame);

    if (reducedMotion) {
      renderStatic(frame);
      await sleep(6500);
      if (myToken !== runToken) return;
      return advance();
    }

    await typeText(frame.cmdEl, frame.command, 22);
    if (myToken !== runToken) return;
    await sleep(550);
    if (myToken !== runToken) return;
    await typeText(frame.outEl, frame.output, 5);
    if (myToken !== runToken) return;
    await sleep(3200);
    if (myToken !== runToken) return;
    advance();
  }

  function advance() {
    currentIndex = (currentIndex + 1) % frames.length;
    playFrame(currentIndex);
  }

  // Manual tab clicks: pause cycling, switch instantly, then resume.
  tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => {
      aborted = true;
      runToken += 1;
      currentIndex = idx;
      // Show the chosen tab's final state immediately, then resume cycle.
      renderStatic(frames[idx]);
      setActive(idx);
      setTimeout(() => playFrame(idx), 4500);
    });
  });

  // Pause while the tab is hidden; restart when visible.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      aborted = true;
      runToken += 1;
    } else {
      playFrame(currentIndex);
    }
  });

  // Boot.
  playFrame(0);
})();
