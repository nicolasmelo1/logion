// SPDX-License-Identifier: MIT
// Setup-complete handoff claim for logion.sh/setup/complete#hid=...
//
// Reads the single-use handoff id from the URL fragment, strips it immediately,
// and POSTs it to the API claim endpoint. The raw setup token is shown exactly
// once in the primary CTA and never touches the landing server.
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  function getApiBase() {
    var el = document.querySelector("[data-api-base]");
    if (el) return el.getAttribute("data-api-base");
    return window.LOGION_API_BASE || "https://api.logion.sh";
  }

  function parseHandoff() {
    var hash = window.location.hash;
    if (!hash) return null;
    var match = hash.match(/^[#]?hid=([A-Za-z0-9_-]+)$/);
    return match ? match[1] : null;
  }

  function setVisible(selector, visible) {
    var el = document.querySelector(selector);
    if (!el) return;
    el.hidden = !visible;
  }

  function setButtonReady(button, command) {
    if (!button) return;
    button.disabled = false;
    button.setAttribute("data-copy-command", command);
    var cmdEl = button.querySelector("[data-setup-cmd]") || button.querySelector(".cta-cmd");
    if (cmdEl) cmdEl.textContent = command;
  }

  // Invalid, expired, or already-used handoff (or a direct visit with no
  // handoff at all): there is nothing to show here — go back to the home
  // page, where the normal sign-in CTA lives. replace() keeps the dead
  // /setup/complete entry out of the back-button history.
  function goHome() {
    window.location.replace("/");
  }

  function claimHandoff(handoffId) {
    var apiBase = getApiBase();
    var url = apiBase.replace(/\/$/, "") + "/v1/setup/handoff/claim";
    return fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ handoff_id: handoffId }),
    });
  }

  function run() {
    var handoffId = parseHandoff();

    // Strip the fragment so it does not survive in browser history or
    // Referer — even when it is malformed or missing.
    history.replaceState(null, "", window.location.pathname + window.location.search);

    // Direct visit or refresh after a claim: nothing to redeem.
    if (!handoffId) {
      goHome();
      return;
    }

    setVisible("[data-setup-claiming]", true);

    claimHandoff(handoffId)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("claim_failed");
        }
        return response.json();
      })
      .then(function (data) {
        var command = data.install_command;
        var button = document.querySelector("[data-setup-copy]");
        setButtonReady(button, command);
        setVisible("[data-setup-claiming]", false);
        setVisible("[data-setup-warning]", true);
        var navStatus = document.querySelector("[data-setup-nav-status]");
        if (navStatus && data.github_login) {
          navStatus.textContent = "@" + data.github_login;
        }
      })
      .catch(function () {
        goHome();
      });
  }

  ready(run);
})();
