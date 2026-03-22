from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from .versioning import version_key

EXACT_DOC_KINDS = {
    "legacy-namespace",
    "net-overview",
    "networking-sysctl",
    "rst-namespace",
    "sysctl-section",
}
CONTEXT_DOC_KINDS = {"context-mention", "context-proc-block"}
STATUS_ORDER = {
    "none": 0,
    "context": 1,
    "exact": 2,
}


def build_index(raw_dir: Path, output_dir: Path) -> None:
    version_files = sorted(raw_dir.glob("*.json"), key=lambda path: version_key(path.stem))
    output_dir.mkdir(parents=True, exist_ok=True)
    params_dir = output_dir / "params"
    blobs_dir = output_dir / "blobs"
    reset_dir(params_dir)
    reset_dir(blobs_dir)

    versions: list[dict[str, object]] = []
    by_param: dict[str, dict[str, object]] = {}
    blobs: dict[str, dict[str, str]] = {}

    for path in version_files:
        payload = json.loads(path.read_text())
        tag = payload["tag"]
        versions.append(
            {
                "tag": tag,
                "releaseDate": payload["releaseDate"],
            }
        )
        for item in payload["parameters"]:
            name = item["name"]
            slug = slugify_param(name)
            aggregate = by_param.setdefault(
                name,
                {
                    "name": name,
                    "slug": slug,
                    "namespace": item["namespace"],
                    "availableVersions": [],
                    "versions": [],
                },
            )

            support_status = support_status_for_entries(item["docEntries"])
            has_doc = support_status in {"exact", "context"}
            has_source = bool(item["sourceEntries"])

            if has_source or has_doc:
                aggregate["availableVersions"].append(tag)

            doc_refs: list[dict[str, object]] = []
            for entry in sort_doc_entries(item["docEntries"]):
                blob_id = blob_hash(entry["body"])
                blobs.setdefault(blob_id, {"text": entry["body"]})
                doc_refs.append(
                    {
                        "path": entry["doc_path"],
                        "heading": entry["heading"],
                        "blob": blob_id,
                        "lineStart": entry.get("line_start"),
                        "lineEnd": entry.get("line_end"),
                    }
                )

            aggregate["versions"].append(
                {
                    "tag": tag,
                    "hasDoc": has_doc,
                    "hasSource": has_source,
                    "supportStatus": support_status,
                    "docRefs": doc_refs,
                    "sourceRefs": slim_source_refs(item["sourceEntries"]),
                }
            )

    catalog: list[dict[str, object]] = []
    for _name, item in sorted(by_param.items()):
        versions_payload = item["versions"]
        param_payload = {
            "name": item["name"],
            "slug": item["slug"],
            "namespace": item["namespace"],
            "availableVersions": item["availableVersions"],
            "versions": versions_payload,
        }
        catalog.append(
            {
                "name": item["name"],
                "slug": item["slug"],
                "namespace": item["namespace"],
                "availableVersions": item["availableVersions"],
            }
        )
        (params_dir / f"{item['slug']}.json").write_text(json.dumps(param_payload, indent=2, sort_keys=True))

    (output_dir / "versions.json").write_text(json.dumps({"versions": versions}, indent=2, sort_keys=True))
    (output_dir / "catalog.json").write_text(json.dumps({"items": catalog}, indent=2, sort_keys=True))
    for blob_id, payload in blobs.items():
        (blobs_dir / f"{blob_id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True))


def support_status_for_entries(entries: list[dict[str, object]]) -> str:
    kinds = {entry["kind"] for entry in entries if entry.get("body")}
    if kinds & EXACT_DOC_KINDS:
        return "exact"
    if kinds & CONTEXT_DOC_KINDS:
        return "context"
    return "none"


def sort_doc_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        entries,
        key=lambda item: (
            -STATUS_ORDER[support_status_for_entries([item])],
            item["doc_path"],
            item["heading"],
        ),
    )


def slim_source_refs(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "api": entry["api"],
            "data_symbol": entry["data_symbol"],
            "handler_symbol": entry["handler_symbol"],
            "path_segments": entry["path_segments"],
            "source_path": entry["source_path"],
            "table": entry["table"],
        }
        for entry in entries
    ]


def blob_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def slugify_param(name: str) -> str:
    return quote(name, safe="")


def reset_dir(path: Path) -> None:
    if path.exists():
        for child in path.iterdir():
            if child.is_file():
                child.unlink()
    else:
        path.mkdir(parents=True, exist_ok=True)
