import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Tests spawn child processes against the built dist/ artefacts;
    // we keep a single forked worker so PATH/env mutations in one
    // test file do not leak into another running in parallel.
    pool: "forks",
    poolOptions: {
      forks: {
        singleFork: true,
      },
    },
    testTimeout: 15_000,
  },
});
