// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { apply, inject, name } from "../index.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));

/** Minimal Cordis context that records what a plugin registers. */
function fakeContext() {
  const registered = [];
  return { registered, tools: { register: (tool) => registered.push(tool) } };
}

test("declares itself as a dsh bundle pointing at its patch file", () => {
  assert.equal(manifest.dsh.bundle.patch, "config/cordis.patch.yml");
  const patch = readFileSync(join(ROOT, manifest.dsh.bundle.patch), "utf8");
  // The patch loads this package by name, so Node module resolution finds
  // it; a file path would break once pnpm relocates the install.
  assert.match(patch, new RegExp(manifest.name));
});

test("only requests the services it actually uses", () => {
  // Asking for model, sandbox, or storage services it never touches
  // would hand the plugin capabilities it has no reason to hold.
  assert.deepEqual(inject, ["tools"]);
});

test("registers one tool per supported operation", () => {
  const ctx = fakeContext();
  apply(ctx);
  const names = ctx.registered.map((tool) => tool.name).sort();
  assert.deepEqual(names, [
    "logion_acquire",
    "logion_inventory",
    "logion_plan",
    "logion_reconcile",
    "logion_search",
    "logion_show",
  ]);
  assert.equal(name, "logion");
});

test("every tool describes what it does", () => {
  const ctx = fakeContext();
  apply(ctx);
  for (const tool of ctx.registered) {
    assert.ok(tool.description.length > 0, `${tool.name} has no description`);
    assert.equal(typeof tool.execute, "function");
  }
});

test("explains itself instead of failing silently without the CLI", async () => {
  const ctx = fakeContext();
  apply(ctx);
  const search = ctx.registered.find((tool) => tool.name === "logion_search");
  const previous = process.env.PATH;
  // An empty PATH is the "logion is not installed" case.
  process.env.PATH = "";
  try {
    const output = await search.execute({});
    assert.match(output, /not installed/i);
  } finally {
    process.env.PATH = previous;
  }
});

test("ships no credential material in the bundle it publishes", () => {
  const patch = readFileSync(
    join(ROOT, manifest.dsh.bundle.patch),
    "utf8",
  ).toLowerCase();
  for (const marker of ["token", "secret", "password", "api_key", "apikey"]) {
    assert.ok(!patch.includes(marker), `patch mentions ${marker}`);
  }
});
