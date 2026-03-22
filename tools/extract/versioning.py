from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_REMOTE = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git"
DEFAULT_FIRST_TAG = "v2.6.11"
DEFAULT_SAMPLE_TAGS = ["v2.6.39", "v4.20", "v5.2", "v5.3", "v6.8"]
SCHEMA_VERSION = 20


@dataclass(frozen=True, slots=True)
class ReleaseTag:
    name: str
    major: int
    minor: int
    patch: int | None

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch or 0)


def parse_release_tag(tag: str) -> ReleaseTag | None:
    match = re.fullmatch(r"v(\d+)\.(\d+)(?:\.(\d+))?", tag)
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2))
    patch_text = match.group(3)
    patch = int(patch_text) if patch_text is not None else None

    if major == 2 and minor == 6 and patch is None:
        return None
    if major >= 3 and patch is not None:
        return None
    if major == 2 and minor != 6:
        return None
    if major < 2:
        return None
    return ReleaseTag(tag, major, minor, patch)


def sort_release_tags(tags: list[str]) -> list[str]:
    parsed = [parse_release_tag(tag) for tag in tags]
    filtered = [item for item in parsed if item is not None]
    return [item.name for item in sorted(filtered, key=lambda item: item.sort_key)]


def select_release_tags(tags: list[str], first_tag: str = DEFAULT_FIRST_TAG) -> list[str]:
    ordered = sort_release_tags(tags)
    return [tag for tag in ordered if version_key(tag) >= version_key(first_tag)]


def version_key(tag: str) -> tuple[int, int, int]:
    parsed = parse_release_tag(tag)
    if parsed is None:
        raise ValueError(f"Unsupported tag format: {tag}")
    return parsed.sort_key
