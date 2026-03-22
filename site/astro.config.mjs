import { defineConfig } from "astro/config";

function resolveBase() {
  const value = process.env.PUBLIC_BASE?.trim();
  if (!value || value === "/") {
    return "/";
  }
  return `/${value.replace(/^\/+|\/+$/g, "")}/`;
}

function resolveSite() {
  return process.env.PUBLIC_SITE_URL ?? "https://example.com";
}

export default defineConfig({
  output: "static",
  base: resolveBase(),
  site: resolveSite(),
  trailingSlash: "always"
});
