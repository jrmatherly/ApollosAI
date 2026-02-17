import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import importPlugin from "eslint-plugin-import";
import unusedImports from "eslint-plugin-unused-imports";
import i18next from "eslint-plugin-i18next";
import prettierConfig from "eslint-config-prettier";
import prettierPlugin from "eslint-plugin-prettier";
import tanstackQuery from "@tanstack/eslint-plugin-query";

export default tseslint.config(
  // ── Base configs ──────────────────────────────────────────────
  js.configs.recommended,
  ...tseslint.configs.recommended,

  // ── React ─────────────────────────────────────────────────────
  reactPlugin.configs.flat.recommended,
  reactPlugin.configs.flat["jsx-runtime"],

  // ── React Hooks ───────────────────────────────────────────────
  reactHooks.configs["recommended-latest"],

  // ── JSX A11y ──────────────────────────────────────────────────
  jsxA11y.flatConfigs.recommended,

  // ── Import ────────────────────────────────────────────────────
  importPlugin.flatConfigs.recommended,
  importPlugin.flatConfigs.typescript,

  // ── TanStack Query ────────────────────────────────────────────
  ...tanstackQuery.configs["flat/recommended"],

  // ── i18next ───────────────────────────────────────────────────
  i18next.configs["flat/recommended"],

  // ── Project-specific rules ────────────────────────────────────
  {
    files: ["**/*.{ts,tsx,js}"],
    plugins: {
      "unused-imports": unusedImports,
      prettier: prettierPlugin,
    },
    settings: {
      react: { version: "detect" },
      "import/resolver": {
        typescript: {
          project: "./tsconfig.json",
        },
      },
    },
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // ── Carried from .eslintrc plugins ──────────────────────
      "i18next/no-literal-string": "error",
      "unused-imports/no-unused-imports": "error",
      "prettier/prettier": "error",

      // ── TypeScript ──────────────────────────────────────────
      "@typescript-eslint/prefer-optional-chain": "error",
      "@typescript-eslint/no-shadow": "error",
      "@typescript-eslint/no-useless-constructor": "error",

      // ── Security rules (previously from airbnb-base) ────────
      "no-new-func": "error",
      "no-script-url": "error",
      "no-proto": "error",
      "no-extend-native": "error",
      "no-iterator": "error",
      "no-caller": "error",
      "no-octal-escape": "error",

      // ── Best practice rules (previously from airbnb-base) ───
      "eqeqeq": ["error", "always", { null: "ignore" }],
      "no-var": "error",
      "prefer-const": "error",
      "prefer-template": "error",
      "no-console": "warn",
      "no-alert": "error",
      "no-return-assign": ["error", "always"],
      "consistent-return": "error",
      "curly": ["error", "multi-line"],
      "default-case": "error",
      "no-else-return": ["error", { allowElseIf: false }],
      "no-lonely-if": "error",
      "no-multi-assign": "error",
      "prefer-destructuring": ["error", { object: true, array: false }],
      "prefer-rest-params": "error",
      "prefer-spread": "error",
      "yoda": "error",
      "no-shadow": "off", // use @typescript-eslint/no-shadow instead

      // ── Import ──────────────────────────────────────────────
      // Performance: disable slow import rules. TypeScript already
      // validates imports at compile time (typecheck runs before eslint).
      "import/no-unresolved": "off",
      "import/namespace": "off",
      "import/no-cycle": "off",
      // Keep these useful import rules (fast):
      "import/order": ["error", {
        groups: ["builtin", "external", "internal", "parent", "sibling", "index"],
        "newlines-between": "always",
      }],
      "import/no-duplicates": "error",
      "import/first": "error",
      "import/newline-after-import": "error",
      "import/no-mutable-exports": "error",
      "import/no-self-import": "error",
      "import/no-useless-path-segments": "error",
      "import/extensions": [
        "error",
        "ignorePackages",
        { "": "never", ts: "never", tsx: "never" },
      ],
      "import/prefer-default-export": "off",
      "import/no-extraneous-dependencies": "off",

      // ── Core JS overrides (carried from .eslintrc) ─────────
      "no-param-reassign": [
        "error",
        {
          props: true,
          ignorePropertyModificationsFor: ["acc", "state"],
        },
      ],
      "no-restricted-syntax": "off",
      "no-underscore-dangle": "off",

      // ── React (carried from .eslintrc) ─────────────────────
      "react/require-default-props": "off",
      "react/prop-types": "off",
      "react/no-array-index-key": "off",
      "react/react-in-jsx-scope": "off",
      "react-hooks/exhaustive-deps": "off",
      // React quality rules (previously from airbnb):
      "react/self-closing-comp": "error",
      "react/jsx-no-constructed-context-values": "error",
      "react/no-unstable-nested-components": "error",
      "react/jsx-boolean-value": ["error", "never"],
      "react/jsx-curly-brace-presence": ["error", { props: "never", children: "never" }],
      "react/no-danger": "warn",
      "react/jsx-fragments": ["error", "syntax"],
      "react/jsx-no-useless-fragment": "error",

      // ── JSX A11y (carried from .eslintrc) ──────────────────
      "jsx-a11y/no-static-element-interactions": "off",
      "jsx-a11y/click-events-have-key-events": "off",
      "jsx-a11y/label-has-associated-control": [
        2,
        { required: { some: ["nesting", "id"] } },
      ],
    },
  },

  // ── Prettier (MUST be after all presets and project rules) ─────
  prettierConfig,

  // ── Global ignores ────────────────────────────────────────────
  {
    ignores: [
      "build/**",
      "node_modules/**",
      ".react-router/**",
      "coverage/**",
      "public/**",
      "scripts/**",
    ],
  },
);
