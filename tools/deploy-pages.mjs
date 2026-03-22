import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);

const rootDir = process.cwd();
const distDir = resolve(rootDir, "site", "dist");
const branch = process.env.GITHUB_PAGES_BRANCH?.trim() || "gh-pages";
const remote = process.env.GITHUB_PAGES_REMOTE?.trim() || "origin";
const cname = process.env.GITHUB_PAGES_CNAME?.trim() || "";
const siteUrl = process.env.PUBLIC_SITE_URL?.trim() || "";
const base = process.env.PUBLIC_BASE?.trim() || "/";
const dryRun = process.argv.includes("--dry-run");

if (!siteUrl) {
  console.error("Missing PUBLIC_SITE_URL. Example: PUBLIC_SITE_URL=https://sysctl.leommxj.com");
  process.exit(1);
}

run("npm", ["run", "build"]);
await writeFile(resolve(distDir, ".nojekyll"), "");

if (cname) {
  await writeFile(resolve(distDir, "CNAME"), `${cname}\n`);
}

const message = buildCommitMessage();
if (dryRun) {
  console.log("Dry run deploy configuration:");
  console.log(`  PUBLIC_SITE_URL=${siteUrl}`);
  console.log(`  PUBLIC_BASE=${base}`);
  console.log(`  GITHUB_PAGES_BRANCH=${branch}`);
  console.log(`  GITHUB_PAGES_REMOTE=${remote}`);
  if (cname) {
    console.log(`  GITHUB_PAGES_CNAME=${cname}`);
  }
  console.log(`  dist=${distDir}`);
  process.exit(0);
}

const ghPagesArgs = [
  require.resolve("gh-pages/bin/gh-pages.js"),
  "-d",
  distDir,
  "-b",
  branch,
  "-r",
  remote,
  "--dotfiles",
  "-m",
  message
];

if (cname) {
  ghPagesArgs.push("-c", cname);
}

run(process.execPath, ghPagesArgs);

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: rootDir,
    env: process.env,
    stdio: "inherit"
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function buildCommitMessage() {
  const rev = spawnSync("git", ["rev-parse", "--short", "HEAD"], {
    cwd: rootDir,
    encoding: "utf8"
  });
  const sha = rev.status === 0 ? rev.stdout.trim() : "";
  return sha ? `Deploy ${sha}` : "Deploy site";
}
