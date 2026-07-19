import eslint from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: ["build/**", "dist/**"],
  },
  eslint.configs.recommended,
  {
    files: ["static/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      globals: globals.browser,
      sourceType: "script",
    },
    rules: {
      "no-console": "error",
      "no-var": "error",
      "prefer-const": "error",
    },
  },
];
