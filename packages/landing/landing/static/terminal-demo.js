// SPDX-License-Identifier: MIT
// Animated CLI demo for the Logion landing hero.
//
// Each tab autoplays its command (typewriter) followed by its output
// (line-by-line reveal), then pauses and advances to the NEXT tab.
// Clicking a tab pauses auto-cycle, instantly switches to that tab's
// final state, and resumes the cycle from the tab after it.
// Honors prefers-reduced-motion by showing the final frame without typing.

(function () {
  "use strict";

  const root = document.querySelector("[data-terminal-demo]");
  if (!root) return;

  const tabs = Array.from(root.querySelectorAll(".hero-demo__tab"));
  const panels = Array.from(root.querySelectorAll(".hero-demo__panel"));
  if (!tabs.length || !panels.length) return;

  const frames = panels.map((panel) => {
    const cmdEl = panel.querySelector("[data-cmd]");
    const outEl = panel.querySelector("[data-out]");
    return {
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

  let runToken = 0;
  let currentIndex = 0;
  let resumeTimer = null;
  let advanceTimer = null;

  function clearTimers() {
    if (resumeTimer !== null) {
      clearTimeout(resumeTimer);
      resumeTimer = null;
    }
    if (advanceTimer !== null) {
      clearTimeout(advanceTimer);
      advanceTimer = null;
    }
  }

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

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function typeText(el, text, msPerChar, myToken) {
    for (let i = 0; i < text.length; i += 1) {
      if (myToken !== runToken) return false;
      el.textContent += text[i];
      const wait = text[i] === "\n" ? msPerChar * 6 : msPerChar;
      await sleep(wait);
    }
    return true;
  }

  function scheduleAdvance(fromIdx, delayMs) {
    clearTimers();
    advanceTimer = setTimeout(() => {
      advanceTimer = null;
      currentIndex = (fromIdx + 1) % frames.length;
      playFrame(currentIndex);
    }, delayMs);
  }

  async function playFrame(idx) {
    clearTimers();
    const myToken = ++runToken;
    currentIndex = idx;
    setActive(idx);
    const frame = frames[idx];
    clearFrame(frame);

    if (reducedMotion) {
      renderStatic(frame);
      scheduleAdvance(idx, 6500);
      return;
    }

    const cmdOk = await typeText(frame.cmdEl, frame.command, 22, myToken);
    if (!cmdOk) return;
    await sleep(550);
    if (myToken !== runToken) return;
    const outOk = await typeText(frame.outEl, frame.output, 5, myToken);
    if (!outOk) return;
    scheduleAdvance(idx, 3500);
  }

  tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => {
      // Cancel anything in flight: bump the token, kill pending timers.
      runToken += 1;
      clearTimers();
      currentIndex = idx;
      setActive(idx);
      // Show the clicked tab fully typed out — no re-animation.
      renderStatic(frames[idx]);
      // After a generous pause, advance to the NEXT tab so the cycle
      // continues without re-typing the one the user just opened.
      resumeTimer = setTimeout(() => {
        resumeTimer = null;
        const next = (idx + 1) % frames.length;
        currentIndex = next;
        playFrame(next);
      }, 5000);
    });
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      runToken += 1;
      clearTimers();
    } else {
      playFrame(currentIndex);
    }
  });

  playFrame(0);
})();
