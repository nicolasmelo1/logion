// SPDX-License-Identifier: MIT
// Viewport-triggered conversations for the example-led section terminals.

(function () {
  "use strict";

  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  const SPEED = { user: 13, agent: 11, run: 7, out: 3 };

  document.querySelectorAll("[data-section-demo]").forEach((root) => {
    const tabs = Array.from(root.querySelectorAll("[data-section-tab]"));
    const panels = Array.from(root.querySelectorAll("[data-section-panel]"));
    if (!panels.length) return;

    const frames = panels.map((panel) => ({
      panel,
      cursor: panel.querySelector(".hero-demo__cursor"),
      segments: Array.from(panel.querySelectorAll("[data-seg]")).map((el) => ({
        el,
        role: el.dataset.role || "agent",
        text: el.textContent,
      })),
    }));

    let activeIndex = 0;
    let visible = false;
    let runToken = 0;
    let advanceTimer = null;
    const completed = new Set();

    function clearAdvance() {
      if (advanceTimer !== null) {
        clearTimeout(advanceTimer);
        advanceTimer = null;
      }
    }

    function scheduleAdvance(index, delay = 3200) {
      clearAdvance();
      if (tabs.length < 2 || !visible) return;
      advanceTimer = setTimeout(() => {
        advanceTimer = null;
        if (visible) activate((index + 1) % tabs.length);
      }, delay);
    }

    function turnOf(segment) {
      return segment.el.closest(".hero-demo__turn");
    }

    function renderStatic(frame) {
      frame.segments.forEach((segment) => {
        const turn = turnOf(segment);
        if (turn) turn.style.display = "";
        segment.el.textContent = segment.text;
      });
      const chat = frame.panel.querySelector(".hero-demo__chat");
      if (frame.cursor && chat) chat.appendChild(frame.cursor);
    }

    function clearFrame(frame) {
      frame.segments.forEach((segment) => {
        segment.el.textContent = "";
        const turn = turnOf(segment);
        if (turn) turn.style.display = "none";
      });
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async function typeInto(segment, token) {
      for (const character of segment.text) {
        if (token !== runToken || !visible) return false;
        segment.el.textContent += character;
        await sleep(character === "\n" ? SPEED[segment.role] * 4 : SPEED[segment.role]);
      }
      return true;
    }

    async function play(index) {
      const frame = frames[index];
      clearAdvance();
      runToken += 1;
      const token = runToken;

      if (reducedMotion || completed.has(frame.panel)) {
        renderStatic(frame);
        if (!reducedMotion) scheduleAdvance(index, 4200);
        return;
      }

      clearFrame(frame);
      for (const segment of frame.segments) {
        if (token !== runToken || !visible) return;
        const turn = turnOf(segment);
        if (turn) turn.style.display = "";
        if (frame.cursor) segment.el.parentNode.appendChild(frame.cursor);
        if (!(await typeInto(segment, token))) return;
        await sleep(260);
      }
      completed.add(frame.panel);
      scheduleAdvance(index);
    }

    function activate(index, animate = true) {
      activeIndex = index;
      tabs.forEach((tab, tabIndex) => {
        const active = tabIndex === index;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
        tab.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel, panelIndex) => {
        const active = panelIndex === index;
        panel.classList.toggle("is-active", active);
        panel.setAttribute("aria-hidden", active ? "false" : "true");
      });
      if (animate && visible) play(index);
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(index));
      tab.addEventListener("keydown", (event) => {
        let next = index;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") {
          next = (index - 1 + tabs.length) % tabs.length;
        } else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(next);
        tabs[next].focus();
      });
    });

    activate(0, false);
    if (reducedMotion) {
      frames.forEach(renderStatic);
      return;
    }
    frames.forEach(clearFrame);

    if (!("IntersectionObserver" in window)) {
      visible = true;
      play(activeIndex);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible) play(activeIndex);
        else {
          runToken += 1;
          clearAdvance();
        }
      },
      { rootMargin: "-10% 0px -10%", threshold: 0 },
    );
    observer.observe(root);

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        runToken += 1;
        clearAdvance();
      }
      else if (visible) play(activeIndex);
    });
  });
})();
