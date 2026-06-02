// @ts-check
//
// ESLint flat config — mirrors the ruff ruleset used by the Python
// packages in this workspace (line-length 79, complexity 12, plus the
// extend-select families: A, ARG, ASYNC, C4, C901, DTZ, E302, E501,
// ERA, FBT, ICN, ISC, LOG, N, PIE, PT, RET, RUF, SIM, T20, TRY,
// W292) translated to the JS/TS ecosystem.

import js from "@eslint/js";
import vitest from "@vitest/eslint-plugin";
import prettier from "eslint-config-prettier";
import { createTypeScriptImportResolver } from "eslint-import-resolver-typescript";
import importX from "eslint-plugin-import-x";
import nodePlugin from "eslint-plugin-n";
import promise from "eslint-plugin-promise";
import sonarjs from "eslint-plugin-sonarjs";
import unicorn from "eslint-plugin-unicorn";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist/**", "node_modules/**", "coverage/**", "*.tgz"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  unicorn.configs["flat/recommended"],
  importX.flatConfigs.recommended,
  importX.flatConfigs.typescript,
  promise.configs["flat/recommended"],
  nodePlugin.configs["flat/recommended-module"],
  sonarjs.configs.recommended,
  prettier,
  {
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      parserOptions: {
        projectService: {
          allowDefaultProject: ["eslint.config.mjs"],
        },
        tsconfigRootDir: import.meta.dirname,
      },
    },
    settings: {
      "import-x/resolver-next": [
        createTypeScriptImportResolver({
          project: "./tsconfig.json",
          alwaysTryTypes: true,
        }),
      ],
    },
    rules: {
      // ── Layout (E / W292 / E302) — Prettier handles line-length 79.
      "eol-last": ["error", "always"],

      // ── Complexity / size (C901 max-complexity=12 + sane sizes).
      complexity: ["error", 12],
      "sonarjs/cognitive-complexity": ["error", 15],
      "max-depth": ["error", 4],
      "max-lines": [
        "error",
        { max: 500, skipBlankLines: true, skipComments: true },
      ],
      "max-lines-per-function": [
        "error",
        { max: 80, skipBlankLines: true, skipComments: true },
      ],
      "max-params": ["error", 5],

      // ── F / ARG — unused / undef.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          args: "all",
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],

      // ── A — shadow builtins.
      "@typescript-eslint/no-shadow": "error",
      "no-shadow-restricted-names": "error",

      // ── ASYNC — async pitfalls.
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "require-await": "error",

      // ── T20 / LOG — no raw console (except warn/error).
      "no-console": ["error", { allow: ["warn", "error"] }],

      // ── ISC / UP — modern string handling.
      "prefer-template": "error",
      "no-useless-concat": "error",

      // ── RET — return discipline.
      "consistent-return": "error",
      "no-else-return": "error",
      "no-useless-return": "error",

      // ── TRY — throw discipline.
      "@typescript-eslint/only-throw-error": "error",
      "no-useless-catch": "error",
      "unicorn/error-message": "error",
      "unicorn/throw-new-error": "error",
      "unicorn/catch-error-name": "error",

      // ── ERA — commented-out code.
      "sonarjs/no-commented-code": "error",

      // ── PIE / SIM / RUF — misc cleanups.
      "object-shorthand": "error",
      "no-useless-rename": "error",
      "no-lonely-if": "error",
      "no-unneeded-ternary": "error",

      // ── N (pep8-naming).
      "@typescript-eslint/naming-convention": [
        "error",
        {
          selector: "default",
          format: ["camelCase"],
          leadingUnderscore: "allow",
        },
        {
          selector: "variable",
          format: ["camelCase", "UPPER_CASE", "PascalCase"],
          leadingUnderscore: "allow",
        },
        { selector: "typeLike", format: ["PascalCase"] },
        { selector: "enumMember", format: ["UPPER_CASE", "PascalCase"] },
        {
          selector: "import",
          format: ["camelCase", "PascalCase"],
        },
        {
          selector: "objectLiteralProperty",
          format: null,
        },
      ],

      // ── I / I001 — import order.
      "import-x/order": [
        "error",
        {
          groups: [
            "builtin",
            "external",
            "internal",
            "parent",
            "sibling",
            "index",
          ],
          "newlines-between": "always",
          alphabetize: { order: "asc", caseInsensitive: true },
        },
      ],
      "import-x/no-duplicates": "error",
      "import-x/no-default-export": "off",

      // ── Local relaxations.
      "unicorn/prevent-abbreviations": "off",
      "unicorn/prefer-top-level-await": "off",
      // tsup emits CJS, so __dirname is legitimate.
      "unicorn/prefer-module": "off",
      // We use `null` to mean "explicit absence" in resolver/detect
      // helpers, matching the surrounding Python idiom.
      "unicorn/no-null": "off",
      "n/no-missing-import": "off",
      "n/no-unpublished-import": "off",
      // CLI entry points legitimately call process.exit.
      "n/no-process-exit": "off",
      "unicorn/no-process-exit": "off",
    },
  },
  {
    files: ["test/**/*.ts"],
    plugins: { vitest },
    rules: {
      ...vitest.configs.recommended.rules,
      "max-lines-per-function": "off",
      "max-lines": "off",
      "sonarjs/no-duplicate-string": "off",
      "sonarjs/cognitive-complexity": "off",
      // Tests spawn child processes; constructing throwaway argv
      // arrays is the natural pattern, not a code smell.
      "no-console": "off",
    },
  },
  {
    files: ["eslint.config.mjs", "vitest.config.ts", "tsup.config.ts"],
    rules: {
      "import-x/no-default-export": "off",
      "import-x/no-named-as-default": "off",
      "import-x/no-named-as-default-member": "off",
      "@typescript-eslint/naming-convention": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "sonarjs/deprecation": "off",
      "n/no-unsupported-features/node-builtins": "off",
    },
  },
);
