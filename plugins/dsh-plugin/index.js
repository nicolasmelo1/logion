// SPDX-License-Identifier: MIT
import { execFile } from "node:child_process";

import { defineTool } from "@deepseek-ai/dsh-tools";

export const name = "logion";

export const inject = ["tools"];

/**
 * The wrapper holds no business logic: every operation shells to the
 * public `logion` CLI with `--json` and renders what it returns. There is
 * no second code path that could drift from what the CLI does, and no
 * Logion credential ever reaches a Cordis config entry — the locally
 * configured CLI owns authentication.
 */
const OPERATIONS = {
  search: {
    argv: ["resources", "search"],
    description:
      "Search the Logion catalog for a resource. Returns first-party " +
      "catalog data only.",
  },
  show: {
    argv: ["resources", "show"],
    description:
      "Show what Logion observed about one resource: source, version, " +
      "revision, digest, license, and publisher-declared permissions.",
  },
  plan: {
    argv: ["resources", "acquire"],
    description:
      "Preview an acquisition without writing anything. Shows the " +
      "channel, revision, digest, declared permissions, and exact argv.",
  },
  acquire: {
    argv: ["resources", "acquire", "--no-dry-run"],
    description:
      "Acquire a resource through its native manager. Only run this " +
      "after a human has reviewed the plan.",
  },
  inventory: {
    argv: ["resources", "inventory"],
    description: "List what Logion recorded as installed locally.",
  },
  reconcile: {
    argv: ["resources", "reconcile"],
    description:
      "Match existing native installations to catalog resources. " +
      "Read-only: it never installs, moves, or rewrites anything.",
  },
};

const MISSING_CLI =
  "The Logion CLI is not installed. Install logion-cli and retry; this " +
  "plugin runs the local CLI and does nothing on its own.";

function runLogion(argv) {
  return new Promise((resolve) => {
    execFile(
      "logion",
      [...argv, "--json"],
      { shell: false, maxBuffer: 8 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error && error.code === "ENOENT") {
          resolve({ ok: false, error: MISSING_CLI });
          return;
        }
        if (error) {
          resolve({ ok: false, error: (stderr || String(error)).trim() });
          return;
        }
        try {
          resolve({ ok: true, data: JSON.parse(stdout) });
        } catch {
          resolve({ ok: false, error: "logion returned non-JSON output" });
        }
      },
    );
  });
}

export function apply(ctx) {
  for (const [operation, spec] of Object.entries(OPERATIONS)) {
    ctx.tools.register(
      defineTool({
        name: `logion_${operation}`,
        description: spec.description,
        parameters: {
          // `required` is omitted rather than set to false: the harness
          // rejects a schema that declares it as anything but true.
          args: {
            type: "array",
            items: { type: "string" },
            description:
              "Extra arguments passed through to the logion CLI verbatim.",
          },
        },
        output: {
          schema: { type: "string" },
          render: (_args, value) => [{ type: "text", text: value }],
        },
        async execute(args) {
          const extra = Array.isArray(args.args) ? args.args.map(String) : [];
          const result = await runLogion([...spec.argv, ...extra]);
          if (!result.ok) {
            return result.error;
          }
          return JSON.stringify(result.data, null, 2);
        },
      }),
    );
  }
}
