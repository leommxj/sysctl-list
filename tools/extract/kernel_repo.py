from __future__ import annotations

import subprocess
from pathlib import Path

from .versioning import DEFAULT_REMOTE, select_release_tags

TAG_FETCH_BATCH_SIZE = 32


class KernelRepo:
    def __init__(self, repo_dir: Path, remote_url: str = DEFAULT_REMOTE) -> None:
        self.repo_dir = repo_dir
        self.remote_url = remote_url

    def ensure_initialized(self) -> None:
        if (self.repo_dir / ".git").exists():
            return
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q")
        self.git("remote", "add", "origin", self.remote_url)

    def git(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_dir), *args],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout

    def git_lines(self, *args: str) -> list[str]:
        return [line for line in self.git(*args).splitlines() if line.strip()]

    def list_remote_release_tags(self) -> list[str]:
        output = subprocess.run(
            ["git", "ls-remote", "--tags", self.remote_url],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        tags: list[str] = []
        for line in output.splitlines():
            ref = line.split("\t", 1)[-1]
            if not ref.startswith("refs/tags/"):
                continue
            tag = ref.removeprefix("refs/tags/").removesuffix("^{}")
            tags.append(tag)
        return select_release_tags(sorted(set(tags)))

    def has_tag(self, tag: str) -> bool:
        result = subprocess.run(
            ["git", "-C", str(self.repo_dir), "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def fetch_tags(self, tags: list[str]) -> None:
        if not tags:
            return
        refspecs = [f"refs/tags/{tag}:refs/tags/{tag}" for tag in tags]
        self.git("fetch", "-q", "--depth", "1", "origin", *refspecs)

    def ensure_tags(self, tags: list[str]) -> None:
        self.ensure_initialized()
        missing = [tag for tag in tags if not self.has_tag(tag)]
        for offset in range(0, len(missing), TAG_FETCH_BATCH_SIZE):
            self.fetch_tags(missing[offset : offset + TAG_FETCH_BATCH_SIZE])

    def resolve_tag(self, tag: str) -> str:
        return self.git("rev-parse", f"{tag}^{{}}").strip()

    def commit_date(self, tag: str) -> str:
        return self.git("log", "-1", "--format=%cI", f"{tag}^{{}}").strip()

    def list_files(self, tag: str, root: str) -> list[str]:
        return self.git_lines("ls-tree", "-r", "--name-only", f"{tag}^{{}}", root)

    def ls_tree(self, tag: str, paths: list[str]) -> list[str]:
        if not paths:
            return []
        return self.git_lines("ls-tree", "-r", f"{tag}^{{}}", "--", *paths)

    def show_text(self, tag: str, path: str) -> str:
        return self.git("show", f"{tag}^{{}}:{path}")

    def grep_files(self, tag: str, pattern: str) -> list[str]:
        return self.grep_paths(tag, pattern, "*.c")

    def grep_paths(
        self,
        tag: str,
        pattern: str,
        *pathspecs: str,
        fixed: bool = False,
        ignore_case: bool = False,
    ) -> list[str]:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.repo_dir),
                "grep",
                "-l",
                "-I",
                "-F" if fixed else "-E",
                *(["-i"] if ignore_case else []),
                pattern,
                f"{tag}^{{}}",
                "--",
                *pathspecs,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
        paths: list[str] = []
        prefix = f"{tag}^{{}}:"
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            paths.append(line.removeprefix(prefix))
        return paths
