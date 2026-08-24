#!/usr/bin/env node
// SPDX-License-Identifier: MIT
/**
 * Node binding for the Logion consented-observation reporter.
 *
 * Dependency-free ES module — no npm imports, no CLI imports.
 *
 * The reporter reads a hook payload from stdin, checks consent, builds
 * an event from the profile's `fields` allowlist only, appends to a
 * bounded local spool, and (under `allow` mode) batches asynchronously
 * to the profile endpoint with TLS verification.
 *
 * Subcommands exposed on the same file:
 *
 *   status   — show whether observation is on, the spool size, and tier.
 *   pending  — list spooled event IDs not yet delivered.
 *   export   — dump the entire local spool as JSON to stdout.
 *   delete   — erase the local spool and consent record.
 *   disable  — set consent mode to `off` in `.logion/consent.json`.
 *
 * Exit 0 always on the hook path, regardless of success or failure.
 */

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync, mkdirSync, statSync, unlinkSync, } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_STDIN_BYTES = 1024 * 1024; // 1 MiB
const DEFAULT_MAX_SPOOL_BYTES = 262144;
const DEFAULT_MAX_BATCH = 20;
const DNT_VARS = ["DO_NOT_TRACK", "LOGION_DO_NOT_TRACK"];
const DNT_FALSE = new Set(["", "0", "false", "no", "off"]);
const MAX_RETRIES = 3;
const BACKOFF_BASE = 100; // ms

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function logionDir(base) {
  return join(base || process.cwd(), ".logion");
}

function consentPath(base) {
  return join(logionDir(base), "consent.json");
}

function spoolPath(base) {
  return join(logionDir(base), "spool.jsonl");
}

function profilePath(base) {
  return join(logionDir(base), "profile.json");
}

function dntActive() {
  for (const v of DNT_VARS) {
    const val = process.env[v] || "";
    if (!DNT_FALSE.has(val)) return true;
  }
  return false;
}

function loadJSON(path) {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return null;
  }
}

function loadConsent(base) {
  return loadJSON(consentPath(base));
}

function loadProfile(base) {
  return loadJSON(profilePath(base));
}

function eventID(payload, installationID) {
  const raw = JSON.stringify({
    payload,
    installation_id: installationID,
  });
  return createHash("sha256").update(raw).digest("hex").slice(0, 32);
}

const SENSITIVE_KEYS = new Set([
  "prompt", "file_content", "local_path", "tool_arguments",
  "tool_results", "model_context", "secrets", "user_identity",
  "transcript_path", "tool_input", "tool_response",
]);

const FIELD_MAP = {
  resource_id: "resource_id",
  resource_version: "resource_version",
  distribution_digest: "distribution_digest",
  event: "event",
  outcome: "outcome",
  duration_bucket: "duration_bucket",
  harness: "harness",
  integration_version: "integration_version",
};

function buildEvent(payload, profile, consent) {
  const allowed = new Set(profile.fields || []);
  const installationID = consent.installation_id || "";
  const eid = eventID(payload, installationID);

  const event = {
    event_id: eid,
    installation_id: installationID,
    timestamp: Date.now() / 1000,
    delivered: false,
  };

  for (const field of allowed) {
    const src = FIELD_MAP[field] || field;
    if (src in payload) {
      event[field] = String(payload[src]);
    }
  }

  // Never include sensitive keys.
  for (const key of SENSITIVE_KEYS) {
    delete event[key];
  }

  return event;
}

function appendSpool(event, base, maxSpool) {
  const spool = spoolPath(base);
  try {
    mkdirSync(dirname(spool), { recursive: true });
  } catch {
    return false;
  }

  const line = JSON.stringify(event) + "\n";
  const lineBytes = Buffer.byteLength(line, "utf-8");

  try {
    if (existsSync(spool)) {
      const current = statSync(spool).size;
      if (current + lineBytes > maxSpool) {
        trimSpool(spool, maxSpool, lineBytes);
      }
    }
    // Append
    const existing = existsSync(spool) ? readFileSync(spool, "utf-8") : "";
    writeFileSync(spool, existing + line, "utf-8");
  } catch {
    return false;
  }
  return true;
}

function trimSpool(spool, maxSpool, incoming) {
  try {
    const content = readFileSync(spool, "utf-8");
    let lines = content.split("\n");
    // Remove trailing empty from split
    if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();

    let dropCount = 0;
    let totalSize = Buffer.byteLength(lines.join("\n") + "\n", "utf-8");
    while (lines.length > 0 && totalSize + incoming > maxSpool) {
      lines.shift();
      dropCount++;
      totalSize = Buffer.byteLength(lines.join("\n") + "\n", "utf-8");
    }

    if (dropCount > 0) {
      const meta = JSON.stringify({
        _drop_count: dropCount,
        _trimmed_at: Date.now() / 1000,
      });
      writeFileSync(spool, meta + "\n" + lines.join("\n") + (lines.length > 0 ? "\n" : ""), "utf-8");
    }
  } catch {
    // ignore
  }
}

function readSpool(base) {
  const spool = spoolPath(base);
  if (!existsSync(spool)) return [];
  const events = [];
  try {
    const content = readFileSync(spool, "utf-8");
    for (const line of content.split("\n")) {
      if (!line.trim()) continue;
      const obj = JSON.parse(line);
      if (typeof obj === "object" && obj !== null && !("_drop_count" in obj)) {
        events.push(obj);
      }
    }
  } catch {
    // ignore
  }
  return events;
}

function writeConsent(consent, base) {
  const path = consentPath(base);
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(consent, null, 2) + "\n", "utf-8");
  } catch {
    return false;
  }
  return true;
}

function deleteSpool(base) {
  const spool = spoolPath(base);
  try {
    if (existsSync(spool)) unlinkSync(spool);
  } catch {
    return false;
  }
  return true;
}

function dedupKey(event) {
  return `${event.event_id || ""}:${event.installation_id || ""}`;
}

function markDelivered(deliveredIds, base) {
  const spool = spoolPath(base);
  if (!existsSync(spool)) return;
  const events = readSpool(base);
  let changed = false;
  for (const ev of events) {
    if (deliveredIds.has(ev.event_id) && !ev.delivered) {
      ev.delivered = true;
      changed = true;
    }
  }
  if (changed) {
    try {
      const lines = events.map((e) => JSON.stringify(e)).join("\n");
      writeFileSync(spool, lines + (lines ? "\n" : ""), "utf-8");
    } catch {
      // ignore
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function uploadBatch(events, endpoint) {
  if (!endpoint.startsWith("https://")) return false;
  const payload = JSON.stringify({ events });

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const url = new URL(endpoint);
      const mod = await import(url.protocol === "https:" ? "node:https" : "node:http");
      const res = await new Promise((resolve, reject) => {
        const req = mod.request(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) },
          timeout: 5000,
        }, (response) => {
          let body = "";
          response.on("data", (chunk) => { body += chunk; });
          response.on("end", () => resolve({ status: response.statusCode, body }));
        });
        req.on("error", reject);
        req.on("timeout", () => { req.destroy(); reject(new Error("timeout")); });
        req.write(payload);
        req.end();
      });
      if (res.status >= 200 && res.status < 300) return true;
    } catch {
      // retry
    }
    await sleep(BACKOFF_BASE * (2 ** attempt));
  }
  return false;
}

// ---------------------------------------------------------------------------
// Hook path
// ---------------------------------------------------------------------------

async function runHook(base) {
  // 1. Read stdin, bounded to 1 MiB. Parse failure → exit 0 silently.
  let raw = "";
  try {
    // Read from stdin synchronously
    const fd = 0;
    const buf = Buffer.alloc(MAX_STDIN_BYTES);
    const fs = await import("node:fs");
    const { readSync } = fs;
    let total = 0;
    while (total < MAX_STDIN_BYTES) {
      let n;
      try {
        n = readSync(fd, buf, total, MAX_STDIN_BYTES - total, null);
      } catch {
        break;
      }
      if (n <= 0) break;
      total += n;
    }
    raw = buf.slice(0, total).toString("utf-8");
  } catch {
    return 0;
  }

  if (!raw.trim()) return 0;

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return 0;
  }
  if (typeof payload !== "object" || payload === null) return 0;

  // 2. Check consent.
  if (dntActive()) return 0;
  const consent = loadConsent(base);
  if (!consent) return 0;
  const mode = consent.mode || "off";
  if (mode === "off") return 0;

  const profile = loadProfile(base);
  if (!profile) return 0;

  // 3. Build event from allowlist only.
  const event = buildEvent(payload, profile, consent);

  // 4. Append to bounded spool.
  const maxSpool = (profile.delivery && profile.delivery.max_spool_bytes) || DEFAULT_MAX_SPOOL_BYTES;
  appendSpool(event, base, maxSpool);

  // 5. Under local-only, stop here.
  if (mode === "local-only") return 0;

  // 6. Under allow, batch async with retries.
  if (mode === "allow") {
    const events = readSpool(base);
    const pending = events.filter((e) => !e.delivered);
    const seen = new Set();
    const unique = [];
    for (const ev of pending) {
      const key = dedupKey(ev);
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(ev);
      }
    }

    const endpoint = (profile.delivery && profile.delivery.endpoint) || "";
    if (endpoint.startsWith("https://")) {
      const maxBatch = (profile.delivery && profile.delivery.max_batch) || DEFAULT_MAX_BATCH;
      const delivered = new Set();
      for (let i = 0; i < unique.length; i += maxBatch) {
        const batch = unique.slice(i, i + maxBatch);
        const ok = await uploadBatch(batch, endpoint);
        if (ok) {
          for (const ev of batch) {
            delivered.add(ev.event_id);
          }
        }
      }
      if (delivered.size > 0) {
        markDelivered(delivered, base);
      }
    }
  }

  // 7. Exit 0 always.
  return 0;
}

// ---------------------------------------------------------------------------
// Subcommands
// ---------------------------------------------------------------------------

function cmdStatus(base) {
  const consent = loadConsent(base);
  const mode = consent ? (consent.mode || "off") : "off";
  const spool = spoolPath(base);
  let spoolSize = 0;
  try { if (existsSync(spool)) spoolSize = statSync(spool).size; } catch {}
  const events = readSpool(base);
  const pendingCount = events.filter((e) => !e.delivered).length;
  const profile = loadProfile(base);
  let tier = "unsupported";
  if (profile && mode !== "off") tier = mode;
  console.log(JSON.stringify({
    mode,
    tier,
    spool_bytes: spoolSize,
    spool_events: events.length,
    pending: pendingCount,
    dnt: dntActive(),
  }, null, 2));
  return 0;
}

function cmdPending(base) {
  const events = readSpool(base);
  const pending = events
    .filter((e) => !e.delivered)
    .map((e) => ({ event_id: e.event_id, event: e.event }));
  console.log(JSON.stringify(pending, null, 2));
  return 0;
}

function cmdExport(base) {
  const events = readSpool(base);
  console.log(JSON.stringify(events, null, 2));
  return 0;
}

function cmdDelete(base) {
  deleteSpool(base);
  const consent = loadConsent(base);
  if (consent) {
    consent.mode = "off";
    writeConsent(consent, base);
  }
  console.log(JSON.stringify({ deleted: true }));
  return 0;
}

function cmdDisable(base) {
  const consent = loadConsent(base) || {};
  consent.mode = "off";
  writeConsent(consent, base);
  console.log(JSON.stringify({ disabled: true }));
  return 0;
}

// ---------------------------------------------------------------------------
// CLI dispatch
// ---------------------------------------------------------------------------

async function main(argv) {
  const args = argv || process.argv.slice(2);

  // Find --base
  let base = null;
  const filteredArgs = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--base" && i + 1 < args.length) {
      base = args[i + 1];
      i++;
    } else {
      filteredArgs.push(args[i]);
    }
  }

  const command = filteredArgs[0];

  switch (command) {
    case "status":
      return cmdStatus(base);
    case "pending":
      return cmdPending(base);
    case "export":
      return cmdExport(base);
    case "delete":
      return cmdDelete(base);
    case "disable":
      return cmdDisable(base);
    default:
      // No subcommand → hook path (read stdin).
      return runHook(base);
  }
}

main().then((code) => {
  process.exit(code);
}).catch(() => {
  process.exit(0);
});