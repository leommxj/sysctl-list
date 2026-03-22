import json
import unittest
from pathlib import Path

from tools.extract.versioning import version_key


class GeneratedDataTests(unittest.TestCase):
    def test_catalog_contains_expected_keys(self) -> None:
        catalog = json.loads(Path("data/generated/catalog.json").read_text())
        names = {item["name"] for item in catalog["items"]}
        self.assertIn("kernel.core_pattern", names)
        self.assertIn("vm.swappiness", names)
        self.assertIn("net.ipv4.ip_forward", names)

    def test_catalog_payload_is_trimmed_for_explorer(self) -> None:
        catalog = json.loads(Path("data/generated/catalog.json").read_text())
        item = next(entry for entry in catalog["items"] if entry["name"] == "vm.swappiness")
        self.assertEqual(set(item), {"availableVersions", "name", "namespace", "slug"})
        self.assertEqual(item["slug"], "vm.swappiness")
        self.assertNotIn("aliases", item)
        self.assertNotIn("summary", item)

    def test_param_payload_uses_minimal_detail_schema(self) -> None:
        payload = json.loads(Path("data/generated/params/vm.swappiness.json").read_text())
        self.assertEqual(set(payload), {"availableVersions", "name", "namespace", "slug", "versions"})
        self.assertNotIn("aliases", payload)
        self.assertNotIn("summary", payload)

        version = next(item for item in payload["versions"] if item["docRefs"] or item["sourceRefs"])
        self.assertEqual(set(version), {"docRefs", "hasDoc", "hasSource", "sourceRefs", "supportStatus", "tag"})

        if version["docRefs"]:
            self.assertEqual(set(version["docRefs"][0]), {"blob", "heading", "lineEnd", "lineStart", "path"})
        if version["sourceRefs"]:
            self.assertEqual(
                set(version["sourceRefs"][0]),
                {"api", "data_symbol", "handler_symbol", "path_segments", "source_path", "table"},
            )

    def test_versions_payload_exists(self) -> None:
        versions = json.loads(Path("data/generated/versions.json").read_text())
        tags = [item["tag"] for item in versions["versions"]]
        self.assertGreaterEqual(len(tags), 110)
        self.assertEqual(tags[0], "v2.6.11")
        self.assertEqual(tags, sorted(tags, key=version_key))
        self.assertEqual(len(tags), len(set(tags)))
        for tag in ("v2.6.39", "v4.4", "v5.2", "v6.8"):
            self.assertIn(tag, tags)
        self.assertEqual(set(versions["versions"][0]), {"releaseDate", "tag"})

    def test_blob_payload_contains_only_text(self) -> None:
        params_dir = Path("data/generated/params")
        sample_path = next(params_dir.glob("*.json"))
        payload = json.loads(sample_path.read_text())
        blob_ref = next(
            ref["blob"]
            for version in payload["versions"]
            for ref in version["docRefs"]
        )
        blob = json.loads((Path("data/generated/blobs") / f"{blob_ref}.json").read_text())
        self.assertEqual(set(blob), {"text"})


if __name__ == "__main__":
    unittest.main()
