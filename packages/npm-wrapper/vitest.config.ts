import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Integration-style tests that spawn child processes — not unit-mockable.
    // Each test file gets its own pool to avoid PATH/env pollution.
    pool: "forks",
    poolOptions: {
      forks: {
        singleFork: true,
      },
    },
    testTimeout: 15_000,
  },
});