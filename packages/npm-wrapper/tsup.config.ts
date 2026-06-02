import { defineConfig } from "tsup";

// All entry points run as CLI scripts (bin shims, lifecycle hooks).
// CJS format is used because:
// 1. #!/usr/bin/env node shebang works natively in CJS (it's just a comment)
// 2. __dirname is available without import.meta.url gymnastics
// 3. No ESM node: import resolution quirks
export default defineConfig([
  // CLI binaries — need shebang on line 1
  {
    entry: {
      "bin/logion": "src/bin/logion.ts",
      "bin/lgn": "src/bin/lgn.ts",
    },
    format: ["cjs"],
    target: "node22",
    platform: "node",
    splitting: false,
    sourcemap: false,
    dts: false,
    clean: true,
    banner: {
      js: "#!/usr/bin/env node",
    },
  },
  // Lifecycle scripts — no shebang needed (run via `node dist/scripts/xxx.js`)
  {
    entry: {
      "scripts/postinstall": "src/scripts/postinstall.ts",
      "scripts/uninstall": "src/scripts/uninstall.ts",
      "scripts/version-from-manifest": "src/scripts/version-from-manifest.ts",
    },
    format: ["cjs"],
    target: "node22",
    platform: "node",
    splitting: false,
    sourcemap: false,
    dts: false,
    clean: false,
  },
]);
