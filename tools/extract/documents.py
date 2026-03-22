from __future__ import annotations

import re
from pathlib import Path

from .models import DocRecord

EXACT_DOC_PATTERNS = (
    re.compile(r"^Documentation/sysctl/[^/]+\.(txt|rst)$"),
    re.compile(r"^Documentation/admin-guide/sysctl/[^/]+\.(txt|rst)$"),
    re.compile(r"^Documentation/networking/[^/]*sysctl[^/]*\.(txt|rst)$"),
)

TEXT_DOC_SUFFIXES = {".rst", ".txt"}
SKIP_DOCS = {"00-INDEX", "README", "index.rst"}
CONTEXT_ENTRY_LINE = re.compile(r"^\s*([-A-Za-z0-9_./*]+)\s*(?:\([^\n]*\))?\s*$")
PARAM_LINE = re.compile(r"^([A-Za-z0-9_./*-]+)\s+-\s+[A-Z][A-Z0-9 ()/_-]*$")
PROC_SYS_PATH = re.compile(r"/proc/sys/([A-Za-z0-9_./*-]+)")
CONF_SCOPE_LINE = re.compile(r"^conf/(?:all|default|interface)/\*(?:\s+.*)?$")


def relevant_doc_paths(paths: list[str]) -> list[str]:
    selected: list[str] = []
    for path in paths:
        if any(pattern.match(path) for pattern in EXACT_DOC_PATTERNS):
            selected.append(path)
    return sorted(selected)


def contextual_doc_paths(paths: list[str], matched_paths: list[str]) -> list[str]:
    matched = set(matched_paths)
    selected: list[str] = []
    for path in paths:
        if path not in matched or "/translations/" in path:
            continue
        if any(pattern.match(path) for pattern in EXACT_DOC_PATTERNS):
            continue
        if Path(path).name in SKIP_DOCS:
            continue
        if path.startswith("Documentation/") and Path(path).suffix in TEXT_DOC_SUFFIXES:
            selected.append(path)
    return sorted(selected)


def parse_document(path: str, text: str) -> list[DocRecord]:
    basename = Path(path).name
    if basename in SKIP_DOCS:
        return []
    if path.startswith("Documentation/networking/"):
        return parse_networking_sysctl(path, text)
    if basename in {"net.txt", "net.rst"}:
        return parse_net_overview(path, text)
    if basename.endswith(".rst"):
        return parse_namespace_rst(path, text)
    return parse_namespace_txt(path, text)


def parse_context_document(path: str, text: str, targets: set[str]) -> list[DocRecord]:
    if not targets:
        return []
    exact_records = parse_sysctl_sections(path, text, targets)
    covered = {record.name for record in exact_records}
    proc_block_records = parse_proc_sys_blocks(path, text, targets - covered)
    covered.update(record.name for record in proc_block_records)
    mention_records = parse_context_mentions(path, text, targets - covered)
    return dedupe_records(exact_records + proc_block_records + mention_records)


def parse_namespace_txt(path: str, text: str) -> list[DocRecord]:
    prefix = namespace_from_path(path)
    blocks = split_on_rule(text.splitlines(), "=")
    records: list[DocRecord] = []
    for block in blocks:
        stripped = [line for line in block if line.strip()]
        if not stripped:
            continue
        heading = stripped[0].strip()
        if not heading.endswith(":"):
            continue
        body = "\n".join(block[block.index(stripped[0]) + 1 :]).strip()
        if not body:
            continue
        records.extend(build_records(prefix, heading[:-1], body, path, "legacy-namespace"))
    return records


def parse_namespace_rst(path: str, text: str) -> list[DocRecord]:
    prefix = namespace_from_path(path)
    records: list[DocRecord] = []
    for heading, underline, body in collect_underlined_sections(text.splitlines()):
        if underline != "=":
            continue
        if "Documentation for /proc/sys/" in heading:
            continue
        if heading in {"Copyright"}:
            continue
        if "/proc/sys/" in heading:
            continue
        if not body.strip():
            continue
        records.extend(build_records(prefix, heading, body, path, "rst-namespace"))
    return records


def parse_net_overview(path: str, text: str) -> list[DocRecord]:
    lines = text.splitlines()
    suffix = Path(path).suffix
    section_rule = "=" if suffix == ".rst" else "-"
    param_rule = "-" if suffix == ".rst" else "-"
    current_prefix = ""
    records: list[DocRecord] = []
    index = 0

    while index < len(lines) - 1:
        heading = lines[index].strip()
        rule = lines[index + 1].strip()
        if heading and is_rule(rule, section_rule) and "/proc/sys/" in heading:
            current_prefix = extract_prefix_from_heading(heading)
            index += 2
            continue
        numbered_section = re.match(r"^\d+\.\s+(.+)$", heading)
        if heading and is_rule(rule, section_rule) and numbered_section and "/proc/sys/" not in heading:
            current_prefix = f"net/{cleanup_heading(numbered_section.group(1)).lower().replace(' ', '-')}"
            index += 2
            continue
        if (
            current_prefix
            and heading
            and is_rule(rule, param_rule)
            and "/proc/sys/" not in heading
            and not re.match(r"^\d+\.", heading)
        ):
            start = index + 2
            end = start
            while end < len(lines):
                if end < len(lines) - 1:
                    next_heading = lines[end].strip()
                    next_rule = lines[end + 1].strip()
                    if next_heading and is_rule(next_rule, section_rule) and "/proc/sys/" in next_heading:
                        break
                    if next_heading and is_rule(next_rule, param_rule) and "/proc/sys/" not in next_heading:
                        break
                end += 1
            body = "\n".join(lines[start:end]).strip()
            if body:
                records.extend(build_records(current_prefix, heading, body, path, "net-overview"))
            index = end
            continue
        index += 1
    return records


def parse_networking_sysctl(path: str, text: str) -> list[DocRecord]:
    lines = text.splitlines()
    records: list[DocRecord] = []
    current_prefix = ""
    current_heading = ""
    current_alias_prefixes: list[str] = []
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, body_lines
        body = "\n".join(body_lines).strip()
        if current_heading and current_prefix and body:
            records.extend(
                build_records(
                    current_prefix,
                    current_heading,
                    body,
                    path,
                    "networking-sysctl",
                    alias_prefixes=current_alias_prefixes,
                )
            )
        current_heading = ""
        body_lines = []

    for line in lines:
        stripped = line.strip()
        prefix = extract_prefix_from_heading(stripped)
        if prefix:
            flush()
            current_prefix = prefix
            current_alias_prefixes = []
            continue
        scope_aliases = networking_scope_aliases(stripped, current_prefix)
        if scope_aliases:
            flush()
            current_alias_prefixes = scope_aliases
            continue
        match = PARAM_LINE.match(stripped)
        if match:
            flush()
            current_heading = match.group(1)
            continue
        if current_heading:
            body_lines.append(line.rstrip())
    flush()
    return records


def parse_sysctl_sections(path: str, text: str, targets: set[str]) -> list[DocRecord]:
    records: list[DocRecord] = []
    for heading, _underline, body in collect_underlined_sections(text.splitlines()):
        if "sysctl" not in heading.lower():
            continue
        records.extend(parse_sysctl_section_body(path, body, targets))
    return dedupe_records(records)


def parse_sysctl_section_body(path: str, body: str, targets: set[str]) -> list[DocRecord]:
    lines = body.splitlines()
    records: list[DocRecord] = []
    index = 0

    while index < len(lines):
        match = CONTEXT_ENTRY_LINE.match(lines[index])
        if not match:
            index += 1
            continue
        heading = cleanup_heading(match.group(1))
        if not looks_like_sysctl_name(heading):
            index += 1
            continue
        start = index + 1
        end = start
        while end < len(lines):
            if CONTEXT_ENTRY_LINE.match(lines[end]):
                break
            end += 1
        entry_body = "\n".join(lines[start:end]).strip()
        entry_records = build_records("", heading, entry_body, path, "sysctl-section")
        for record in entry_records:
            if record.name in targets and record.body:
                records.append(record)
        index = end

    return records


def parse_proc_sys_blocks(path: str, text: str, targets: set[str]) -> list[DocRecord]:
    if not targets:
        return []
    lines = text.splitlines()
    heading = Path(path).stem
    records: list[DocRecord] = []
    seen: set[str] = set()
    index = 0

    while index < len(lines):
        if index < len(lines) - 1:
            next_rule = lines[index + 1].strip()
            if lines[index].strip() and is_uniform_rule(next_rule) and len(next_rule) >= len(lines[index].strip()):
                heading = lines[index].strip()
                index += 2
                continue

        name = standalone_proc_sys_name(lines[index])
        if not name or name not in targets or name in seen:
            index += 1
            continue

        body, line_end = collect_indented_block(lines, index)
        if len(body) < 24:
            index = max(index + 1, line_end)
            continue

        records.append(
            DocRecord(
                name=name,
                namespace=name.split(".", 1)[0],
                aliases=sorted(build_aliases(name, name, "", [])),
                doc_path=path,
                heading=proc_sys_heading(name),
                body=body,
                prefix=name.rsplit(".", 1)[0] if "." in name else "",
                kind="context-proc-block",
                line_start=index + 1,
                line_end=line_end,
            )
        )
        seen.add(name)
        index = max(index + 1, line_end)

    return records


def parse_context_mentions(path: str, text: str, targets: set[str]) -> list[DocRecord]:
    if not targets:
        return []
    paragraphs = collect_paragraphs(text.splitlines(), Path(path).stem)
    records: list[DocRecord] = []
    seen: set[str] = set()

    for heading, paragraph in paragraphs:
        if len(paragraph) < 24:
            continue
        normalized = normalize_body(paragraph)
        for name in sorted(targets):
            if name in seen:
                continue
            proc_path = f"/proc/sys/{name.replace('.', '/')}"
            if name not in normalized and proc_path not in normalized:
                continue
            records.append(
                DocRecord(
                    name=name,
                    namespace=name.split(".", 1)[0],
                    aliases=sorted(build_aliases(name, name, "", [])),
                    doc_path=path,
                    heading=heading,
                    body=normalized,
                    prefix=name.rsplit(".", 1)[0] if "." in name else "",
                    kind="context-mention",
                )
            )
            seen.add(name)

    return records


def build_records(
    prefix: str,
    heading: str,
    body: str,
    doc_path: str,
    kind: str,
    alias_prefixes: list[str] | None = None,
) -> list[DocRecord]:
    names = split_heading_names(heading)
    records: list[DocRecord] = []
    for raw_name in names:
        name = normalize_name(raw_name, prefix)
        if not name:
            continue
        aliases = sorted(build_aliases(name, raw_name, prefix, alias_prefixes or []))
        records.append(
            DocRecord(
                name=name,
                namespace=name.split(".", 1)[0],
                aliases=aliases,
                doc_path=doc_path,
                heading=heading.strip(),
                body=normalize_body(body),
                prefix=prefix.replace("/", "."),
                kind=kind,
            )
        )
    return records


def split_heading_names(heading: str) -> list[str]:
    value = cleanup_heading(heading)
    normalized = re.sub(r",?\s+and\s+", ",", value)
    normalized = normalized.replace(" & ", ",")
    if "," in normalized:
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        if len(parts) > 1 and all(token_is_name(part) for part in parts):
            return parts
    return [value]


def cleanup_heading(heading: str) -> str:
    value = heading.strip().rstrip(":")
    value = re.sub(r"\s+\([^)]*\)$", "", value)
    value = value.replace("``", "")
    return value.strip()


def namespace_from_path(path: str) -> str:
    return Path(path).stem


def normalize_name(raw_name: str, prefix: str) -> str:
    value = cleanup_heading(raw_name)
    value = value.strip("/ ")
    if not value:
        return ""
    if value.startswith("/proc/sys/"):
        return normalize_proc_sys_path(value.removeprefix("/proc/sys/"))
    if prefix:
        return normalize_proc_sys_path(f"{prefix}/{value}")
    return normalize_proc_sys_path(value)


def build_aliases(name: str, raw_name: str, prefix: str, alias_prefixes: list[str]) -> set[str]:
    aliases = {cleanup_heading(raw_name), name, f"/proc/sys/{name.replace('.', '/')}"}
    if prefix:
        aliases.add(prefix.replace("/", "."))
        aliases.add(f"/proc/sys/{prefix.strip('/')}")
    relative = cleanup_heading(raw_name)
    if "/" in relative:
        aliases.add(relative.replace("/", "."))
    alias_leaf = relative.strip("/").split("/")[-1]
    for alias_prefix in alias_prefixes:
        alias_name = normalize_name(alias_leaf, alias_prefix)
        if alias_name:
            aliases.add(alias_name)
            aliases.add(f"/proc/sys/{alias_name.replace('.', '/')}")
    return {alias for alias in aliases if alias}


def normalize_proc_sys_path(value: str) -> str:
    normalized = value.strip().strip("/")
    normalized = re.sub(r"/\*$", "", normalized)
    normalized = re.sub(r"/+", "/", normalized)
    normalized = normalized.replace("/", ".")
    normalized = re.sub(r"\.+", ".", normalized)
    return normalized


def extract_prefix_from_heading(heading: str) -> str:
    match = PROC_SYS_PATH.search(heading)
    if not match:
        return ""
    path = match.group(1)
    path = re.sub(r"/\*$", "", path)
    return path.strip("/")


def networking_scope_aliases(heading: str, current_prefix: str) -> list[str]:
    value = heading.strip().strip(":").replace("`", "")
    if not CONF_SCOPE_LINE.fullmatch(value):
        return []
    root = networking_root_prefix(current_prefix)
    if not root:
        return []
    return [f"{root}/conf/*"]


def networking_root_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    segments = [segment for segment in prefix.strip("/").split("/") if segment]
    if len(segments) >= 2 and segments[0] == "net":
        return "/".join(segments[:2])
    return ""


def normalize_body(body: str) -> str:
    lines = [line.rstrip() for line in body.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def dedent_block(lines: list[str]) -> str:
    content = [line for line in lines if line.strip()]
    if not content:
        return ""
    indent = min(len(line) - len(line.lstrip()) for line in content)
    trimmed = [line[indent:] if line.strip() else "" for line in lines]
    return normalize_body("\n".join(trimmed))


def collect_underlined_sections(lines: list[str]) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = []
    index = 0
    while index < len(lines) - 1:
        heading = lines[index].rstrip()
        rule = lines[index + 1].strip()
        if heading.strip() and is_uniform_rule(rule) and len(rule) >= len(heading.strip()):
            start = index + 2
            end = start
            while end < len(lines):
                if end < len(lines) - 1:
                    next_heading = lines[end].rstrip()
                    next_rule = lines[end + 1].strip()
                    if next_heading.strip() and is_uniform_rule(next_rule) and len(next_rule) >= len(next_heading.strip()):
                        break
                end += 1
            body = "\n".join(lines[start:end]).strip()
            sections.append((heading.strip(), rule[0], body))
            index = end
            continue
        index += 1
    return sections


def collect_paragraphs(lines: list[str], fallback_heading: str) -> list[tuple[str, str]]:
    paragraphs: list[tuple[str, str]] = []
    current: list[str] = []
    heading = fallback_heading
    index = 0

    while index < len(lines):
        if index < len(lines) - 1:
            next_rule = lines[index + 1].strip()
            if lines[index].strip() and is_uniform_rule(next_rule) and len(next_rule) >= len(lines[index].strip()):
                if current:
                    paragraphs.append((heading, "\n".join(current).strip()))
                    current = []
                heading = lines[index].strip()
                index += 2
                continue
        line = lines[index].rstrip()
        if line.strip():
            current.append(line)
        elif current:
            paragraphs.append((heading, "\n".join(current).strip()))
            current = []
        index += 1

    if current:
        paragraphs.append((heading, "\n".join(current).strip()))

    return paragraphs


def split_on_rule(lines: list[str], char: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if is_rule(line.strip(), char):
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def dedupe_records(records: list[DocRecord]) -> list[DocRecord]:
    deduped: dict[tuple[str, str, str, str], DocRecord] = {}
    for record in records:
        key = (record.name, record.doc_path, record.kind, record.body)
        deduped[key] = record
    return list(deduped.values())


def standalone_proc_sys_name(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^(?:[*-]|\d+\.)\s+", "", stripped)
    stripped = stripped.strip("`")
    if not stripped.startswith("/proc/sys/"):
        return ""
    if not re.fullmatch(r"/proc/sys/[A-Za-z0-9_./*-]+", stripped):
        return ""
    return normalize_proc_sys_path(stripped.removeprefix("/proc/sys/"))


def proc_sys_heading(name: str) -> str:
    return f"/proc/sys/{name.replace('.', '/')}"


def collect_indented_block(lines: list[str], start: int) -> tuple[str, int]:
    base_indent = line_indent(lines[start])
    body_lines: list[str] = []
    last_content_index = start
    index = start + 1

    while index < len(lines):
        if index < len(lines) - 1:
            next_rule = lines[index + 1].strip()
            if lines[index].strip() and is_uniform_rule(next_rule) and len(next_rule) >= len(lines[index].strip()):
                break

        line = lines[index].rstrip()
        if not line.strip():
            if body_lines:
                body_lines.append("")
            index += 1
            continue

        if line_indent(line) <= base_indent:
            break

        body_lines.append(line)
        last_content_index = index
        index += 1

    return dedent_block(body_lines), last_content_index + 1


def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def is_uniform_rule(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 3 and len(set(stripped)) == 1 and stripped[0] in "=-~^."


def is_rule(line: str, char: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 3 and set(stripped) == {char}


def token_is_name(value: str) -> bool:
    token = cleanup_heading(value)
    return bool(re.fullmatch(r"[A-Za-z0-9_./*-]+", token))


def looks_like_sysctl_name(value: str) -> bool:
    token = cleanup_heading(value)
    return token.startswith("/proc/sys/") or "." in token or "/" in token
