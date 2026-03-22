from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .documents import contextual_doc_paths, parse_context_document, parse_document, relevant_doc_paths
from .indexer import build_index
from .kernel_repo import KernelRepo
from .source_scan import scan_source_file
from .versioning import DEFAULT_SAMPLE_TAGS, SCHEMA_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.extract")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("sync-tags", "extract-tags", "all"):
        command = subparsers.add_parser(name)
        add_common_args(command)

    build = subparsers.add_parser("build-index")
    build.add_argument("--raw-dir", default="data/raw/versions")
    build.add_argument("--generated-dir", default="data/generated")

    stats = subparsers.add_parser("stats")
    stats.add_argument("--generated-dir", default="data/generated")
    stats.add_argument("--tag", default="")

    sample = subparsers.add_parser("sample")
    add_common_args(sample)
    return parser


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-dir", default="data/cache/linux")
    parser.add_argument("--raw-dir", default="data/raw/versions")
    parser.add_argument("--generated-dir", default="data/generated")
    parser.add_argument("--state-file", default="data/state/extraction-state.json")
    parser.add_argument("--tags", default="")


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "build-index":
        build_index(Path(args.raw_dir), Path(args.generated_dir))
        return
    if args.command == "stats":
        print_stats(Path(args.generated_dir), args.tag)
        return
    if args.command == "sample":
        run_pipeline(args, DEFAULT_SAMPLE_TAGS)
        return
    if args.command == "sync-tags":
        sync_tags(args, parse_tags(args.tags))
        return
    if args.command == "extract-tags":
        extract_tags(args, parse_tags(args.tags))
        return
    if args.command == "all":
        requested = parse_tags(args.tags)
        sync_tags(args, requested)
        extract_tags(args, requested)
        build_index(Path(args.raw_dir), Path(args.generated_dir))


def run_pipeline(args: argparse.Namespace, tags: list[str]) -> None:
    sync_tags(args, tags)
    extract_tags(args, tags)
    build_index(Path(args.raw_dir), Path(args.generated_dir))


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def sync_tags(args: argparse.Namespace, requested: list[str]) -> list[str]:
    repo = KernelRepo(Path(args.repo_dir))
    repo.ensure_initialized()
    tags = requested or repo.list_remote_release_tags()
    repo.ensure_tags(tags)
    return tags


def extract_tags(args: argparse.Namespace, requested: list[str]) -> None:
    repo = KernelRepo(Path(args.repo_dir))
    repo.ensure_initialized()
    tags = requested or repo.list_remote_release_tags()
    repo.ensure_tags(tags)

    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state_file)
    state = load_state(state_path)

    for tag in tags:
        commit = repo.resolve_tag(tag)
        all_doc_paths = repo.list_files(tag, "Documentation")
        exact_doc_paths = relevant_doc_paths(all_doc_paths)
        context_matches = repo.grep_paths(tag, r"/proc/sys/|sysctls?", "Documentation")
        context_doc_candidates = contextual_doc_paths(all_doc_paths, context_matches)
        source_files = repo.grep_files(tag, r"register_[a-z_]*sysctl")
        doc_paths = sorted(set(exact_doc_paths + context_doc_candidates))
        docs_fingerprint = hash_lines(repo.ls_tree(tag, doc_paths))
        source_fingerprint = hash_lines(repo.ls_tree(tag, source_files))
        version_state = state.get(tag)
        output_path = raw_dir / f"{tag}.json"
        if (
            version_state
            and version_state.get("schemaVersion") == SCHEMA_VERSION
            and version_state.get("commit") == commit
            and version_state.get("docsFingerprint") == docs_fingerprint
            and version_state.get("sourceFingerprint") == source_fingerprint
            and output_path.exists()
        ):
            continue

        payload = extract_version(repo, tag, commit, exact_doc_paths, context_doc_candidates, source_files)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        state[tag] = {
            "schemaVersion": SCHEMA_VERSION,
            "commit": commit,
            "docsFingerprint": docs_fingerprint,
            "sourceFingerprint": source_fingerprint,
            "updatedAt": timestamp(),
        }
        save_state(state_path, state)


def extract_version(
    repo: KernelRepo,
    tag: str,
    commit: str,
    exact_doc_paths: list[str],
    context_doc_paths: list[str],
    source_files: list[str],
) -> dict[str, object]:
    aggregate: dict[str, dict[str, object]] = {}

    for path in exact_doc_paths:
        for record in parse_document(path, repo.show_text(tag, path)):
            item = aggregate.setdefault(
                record.name,
                {
                    "name": record.name,
                    "namespace": record.namespace,
                    "aliases": set(),
                    "docEntries": [],
                    "sourceEntries": [],
                },
            )
            item["aliases"].update(record.aliases)
            item["docEntries"].append(record.to_json())

    for path in source_files:
        for record in scan_source_file(path, repo.show_text(tag, path)):
            item = aggregate.setdefault(
                record.name,
                {
                    "name": record.name,
                    "namespace": record.namespace,
                    "aliases": set(),
                    "docEntries": [],
                    "sourceEntries": [],
                },
            )
            item["aliases"].update(record.aliases)
            item["sourceEntries"].append(record.to_json())

    reconcile_simplified_doc_names(aggregate)
    reconcile_alias_source_matches(aggregate)

    unresolved = {
        name
        for name, payload in aggregate.items()
        if payload["sourceEntries"] and not payload["docEntries"]
    }

    for path in context_doc_paths:
        if not unresolved:
            break
        for record in parse_context_document(path, repo.show_text(tag, path), unresolved):
            item = aggregate.get(record.name)
            if item is None or not item["sourceEntries"]:
                continue
            item["aliases"].update(record.aliases)
            item["docEntries"].append(record.to_json())
        unresolved = {
            name
            for name, payload in aggregate.items()
            if payload["sourceEntries"] and not payload["docEntries"]
        }

    parameters: list[dict[str, object]] = []
    for name, payload in sorted(aggregate.items()):
        payload["aliases"] = sorted(payload["aliases"])
        payload["docEntries"] = sorted(payload["docEntries"], key=lambda item: (item["doc_path"], item["heading"]))
        payload["sourceEntries"] = sorted(
            dedupe_source_entries(payload["sourceEntries"]),
            key=lambda item: (item["source_path"], item["api"], item["table"]),
        )
        parameters.append(payload)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "tag": tag,
        "commit": commit,
        "releaseDate": repo.commit_date(tag),
        "extractedAt": timestamp(),
        "documents": sorted(set(exact_doc_paths + context_doc_paths)),
        "sourceFiles": source_files,
        "parameters": parameters,
        "stats": {
            "documentCount": len(set(exact_doc_paths + context_doc_paths)),
            "sourceFileCount": len(source_files),
            "parameterCount": len(parameters),
            "documentedCount": sum(1 for item in parameters if item["docEntries"]),
        },
    }


def dedupe_source_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, object]] = []
    for item in entries:
        key = (item["source_path"], item["api"], item["table"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def reconcile_simplified_doc_names(aggregate: dict[str, dict[str, object]]) -> None:
    moves: list[tuple[str, str]] = []
    for name, payload in sorted(aggregate.items()):
        if not payload["docEntries"] or payload["sourceEntries"]:
            continue
        target = simplified_doc_target(name, aggregate)
        if target:
            moves.append((name, target))

    for source_name, target_name in moves:
        move_doc_entries(aggregate, source_name, target_name)


def reconcile_alias_source_matches(aggregate: dict[str, dict[str, object]]) -> None:
    doc_candidates = {
        name: payload
        for name, payload in aggregate.items()
        if payload["docEntries"] and not payload["sourceEntries"]
    }
    source_candidates = {
        name: payload
        for name, payload in aggregate.items()
        if payload["sourceEntries"] and not payload["docEntries"]
    }
    planned: dict[str, str] = {}

    for doc_name, doc_payload in doc_candidates.items():
        matches = [
            source_name
            for source_name, source_payload in source_candidates.items()
            if strong_aliases(doc_payload).intersection(strong_aliases(source_payload))
        ]
        if len(matches) == 1:
            planned[doc_name] = matches[0]

    if not planned:
        return

    source_use_counts = defaultdict(int)
    for source_name in planned.values():
        source_use_counts[source_name] += 1

    for doc_name, source_name in sorted(planned.items()):
        if source_use_counts[source_name] != 1:
            continue
        move_source_entries(aggregate, source_name, doc_name)


def strong_aliases(payload: dict[str, object]) -> set[str]:
    aliases = payload.get("aliases", [])
    name = payload.get("name", "")
    leaf = name.rsplit(".", 1)[-1] if isinstance(name, str) and name else ""
    return {
        alias
        for alias in aliases
        if isinstance(alias, str) and alias_matches_leaf(alias, leaf)
    }


def alias_matches_leaf(alias: str, leaf: str) -> bool:
    if not leaf:
        return False
    return alias.endswith(f".{leaf}") or alias.endswith(f"/{leaf}")


def simplified_doc_target(name: str, aggregate: dict[str, dict[str, object]]) -> str:
    doc_segments = name.split(".")
    if len(doc_segments) < 3:
        return ""

    candidates: list[str] = []
    for target_name, payload in aggregate.items():
        if target_name == name or not payload["sourceEntries"]:
            continue
        source_segments = target_name.split(".")
        if len(source_segments) != len(doc_segments) + 1:
            continue
        if source_segments[-1] != doc_segments[-1]:
            continue
        if source_segments[: len(doc_segments) - 1] != doc_segments[:-1]:
            continue
        candidates.append(target_name)

    if len(candidates) != 1:
        return ""
    return candidates[0]


def move_doc_entries(
    aggregate: dict[str, dict[str, object]],
    source_name: str,
    target_name: str,
) -> None:
    source = aggregate.get(source_name)
    target = aggregate.get(target_name)
    if source is None or target is None or source_name == target_name:
        return

    target["aliases"].update(source["aliases"])
    target["aliases"].add(source_name)
    target["docEntries"].extend(rewrite_doc_entry_names(source["docEntries"], target_name))
    del aggregate[source_name]


def move_source_entries(
    aggregate: dict[str, dict[str, object]],
    source_name: str,
    target_name: str,
) -> None:
    source = aggregate.get(source_name)
    target = aggregate.get(target_name)
    if source is None or target is None or source_name == target_name:
        return

    target["aliases"].update(source["aliases"])
    target["aliases"].add(source_name)
    target["sourceEntries"].extend(rewrite_source_entry_names(source["sourceEntries"], target_name))
    del aggregate[source_name]


def rewrite_doc_entry_names(entries: list[dict[str, object]], target_name: str) -> list[dict[str, object]]:
    namespace = target_name.split(".", 1)[0]
    prefix = target_name.rsplit(".", 1)[0] if "." in target_name else ""
    rewritten: list[dict[str, object]] = []

    for entry in entries:
        item = dict(entry)
        aliases = set(item.get("aliases", []))
        aliases.add(target_name)
        item["name"] = target_name
        item["namespace"] = namespace
        item["prefix"] = prefix
        item["aliases"] = sorted(aliases)
        rewritten.append(item)

    return rewritten


def rewrite_source_entry_names(entries: list[dict[str, object]], target_name: str) -> list[dict[str, object]]:
    namespace = target_name.split(".", 1)[0]
    rewritten: list[dict[str, object]] = []

    for entry in entries:
        item = dict(entry)
        aliases = set(item.get("aliases", []))
        aliases.add(target_name)
        item["name"] = target_name
        item["namespace"] = namespace
        item["aliases"] = sorted(aliases)
        rewritten.append(item)

    return rewritten


def print_stats(generated_dir: Path, requested_tag: str) -> None:
    versions_path = generated_dir / "versions.json"
    version_payload = json.loads(versions_path.read_text())
    tags = [item["tag"] for item in version_payload["versions"]]
    if not tags:
        raise SystemExit("No generated versions found.")
    target_tag = requested_tag or tags[-1]
    if target_tag not in tags:
        raise SystemExit(f"Unknown generated tag: {target_tag}")

    namespace_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in sorted((generated_dir / "params").glob("*.json")):
        payload = json.loads(path.read_text())
        version = next((item for item in payload["versions"] if item["tag"] == target_tag), None)
        if version is None:
            continue
        namespace = payload["namespace"]
        status = version["supportStatus"]
        namespace_counts[namespace]["total"] += 1
        namespace_counts[namespace][status] += 1

    header = f"Namespace support status ratios for {target_tag}"
    print(header)
    print("=" * len(header))
    print("namespace,total,exact,context,none")
    for namespace in sorted(namespace_counts):
        counts = namespace_counts[namespace]
        total = counts["total"] or 1
        print(
            ",".join(
                [
                    namespace,
                    str(counts["total"]),
                    format_ratio(counts["exact"], total),
                    format_ratio(counts["context"], total),
                    format_ratio(counts["none"], total),
                ]
            )
        )


def format_ratio(count: int, total: int) -> str:
    return f"{count} ({count / total:.1%})"


def load_state(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def hash_lines(lines: list[str]) -> str:
    return hashlib.sha1("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
