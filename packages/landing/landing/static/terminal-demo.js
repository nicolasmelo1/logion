// SPDX-License-Identifier: MIT
// Animated agent-conversation demo for the Logion landing hero.
//
// Each tab autoplays a short conversation between the user and their
// agent (typewriter, one turn at a time), then pauses and advances to
// the NEXT tab. Clicking a tab pauses auto-cycle, instantly switches to
// that tab's final state, and resumes the cycle from the tab after it.
// Honors prefers-reduced-motion by showing the final frame without typing.

(function () {
  "use strict";

  const root = document.querySelector("[data-terminal-demo]");
  if (!root) return;

  const tabs = Array.from(root.querySelectorAll(".hero-demo__tab"));
  const panels = Array.from(root.querySelectorAll(".hero-demo__panel"));
  if (!tabs.length || !panels.length) return;

  // Typing speed (ms per character) per conversation role.
  const SPEED = { you: 16, agent: 14, run: 11, out: 4 };
  const DEFAULT_SPEED = 14;

  const frames = panels.map((panel) => {
    const segEls = Array.from(panel.querySelectorAll("[data-seg]"));
    const segments = segEls.map((el) => ({
      el,
      text: el.textContent,
      role: el.getAttribute("data-role") || "",
    }));
    return {
      panel,
      segments,
      cursor: panel.querySelector(".hero-demo__cursor"),
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
    frame.segments.forEach((seg) => {
      seg.el.textContent = seg.text;
    });
    // Park the cursor at the end of the conversation.
    const chat = frame.panel.querySelector(".hero-demo__chat");
    if (frame.cursor && chat) chat.appendChild(frame.cursor);
  }

  function clearFrame(frame) {
    frame.segments.forEach((seg) => {
      seg.el.textContent = "";
    });
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function typeInto(el, text, msPerChar, myToken) {
    for (let i = 0; i < text.length; i += 1) {
      if (myToken !== runToken) return false;
      el.textContent += text[i];
      const wait = text[i] === "\n" ? msPerChar * 5 : msPerChar;
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
      scheduleAdvance(idx, 7000);
      return;
    }

    for (const seg of frame.segments) {
      if (myToken !== runToken) return;
      // Cursor trails the turn currently being typed.
      if (frame.cursor) seg.el.parentNode.appendChild(frame.cursor);
      const speed = SPEED[seg.role] || DEFAULT_SPEED;
      const ok = await typeInto(seg.el, seg.text, speed, myToken);
      if (!ok) return;
      await sleep(420);
      if (myToken !== runToken) return;
    }
    scheduleAdvance(idx, 4200);
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
      }, 5500);
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
