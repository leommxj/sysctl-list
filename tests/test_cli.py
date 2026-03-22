import unittest

from tools.extract.cli import reconcile_alias_source_matches, reconcile_simplified_doc_names


class CliExtractionTests(unittest.TestCase):
    def test_simplified_doc_names_merge_into_unique_source_target(self) -> None:
        aggregate = {
            "net.ipv4.min_pmtu": {
                "name": "net.ipv4.min_pmtu",
                "namespace": "net",
                "aliases": {"net.ipv4.min_pmtu", "/proc/sys/net/ipv4/min_pmtu", "min_pmtu"},
                "docEntries": [
                    {
                        "name": "net.ipv4.min_pmtu",
                        "namespace": "net",
                        "aliases": ["net.ipv4.min_pmtu", "/proc/sys/net/ipv4/min_pmtu", "min_pmtu"],
                        "doc_path": "Documentation/networking/ip-sysctl.rst",
                        "heading": "min_pmtu",
                        "body": "minimum Path MTU",
                        "prefix": "net.ipv4",
                        "kind": "networking-sysctl",
                    }
                ],
                "sourceEntries": [],
            },
            "net.ipv4.route.min_pmtu": {
                "name": "net.ipv4.route.min_pmtu",
                "namespace": "net",
                "aliases": {"net.ipv4.route.min_pmtu", "/proc/sys/net/ipv4/route/min_pmtu", "min_pmtu"},
                "docEntries": [],
                "sourceEntries": [
                    {
                        "name": "net.ipv4.route.min_pmtu",
                        "namespace": "net",
                        "aliases": ["net.ipv4.route.min_pmtu", "/proc/sys/net/ipv4/route/min_pmtu", "min_pmtu"],
                        "source_path": "net/ipv4/route.c",
                        "api": "register_net_sysctl",
                        "table": "ipv4_route_table",
                        "path_segments": ["net", "ipv4", "route", "min_pmtu"],
                        "data_symbol": "ip_rt_min_pmtu",
                        "handler_symbol": "proc_dointvec",
                        "trail": ["min_pmtu"],
                    }
                ],
            },
        }

        reconcile_simplified_doc_names(aggregate)

        self.assertNotIn("net.ipv4.min_pmtu", aggregate)
        self.assertIn("net.ipv4.route.min_pmtu", aggregate)
        merged = aggregate["net.ipv4.route.min_pmtu"]
        self.assertIn("net.ipv4.min_pmtu", merged["aliases"])
        self.assertEqual(merged["docEntries"][0]["name"], "net.ipv4.route.min_pmtu")
        self.assertEqual(merged["docEntries"][0]["prefix"], "net.ipv4.route")

    def test_simplified_doc_names_do_not_merge_when_multiple_targets_exist(self) -> None:
        aggregate = {
            "net.ipv4.foo": {
                "name": "net.ipv4.foo",
                "namespace": "net",
                "aliases": {"net.ipv4.foo"},
                "docEntries": [{"name": "net.ipv4.foo", "namespace": "net", "aliases": ["net.ipv4.foo"], "prefix": "net.ipv4"}],
                "sourceEntries": [],
            },
            "net.ipv4.route.foo": {
                "name": "net.ipv4.route.foo",
                "namespace": "net",
                "aliases": {"net.ipv4.route.foo"},
                "docEntries": [],
                "sourceEntries": [{"name": "net.ipv4.route.foo"}],
            },
            "net.ipv4.conf.foo": {
                "name": "net.ipv4.conf.foo",
                "namespace": "net",
                "aliases": {"net.ipv4.conf.foo"},
                "docEntries": [],
                "sourceEntries": [{"name": "net.ipv4.conf.foo"}],
            },
        }

        reconcile_simplified_doc_names(aggregate)

        self.assertIn("net.ipv4.foo", aggregate)
        self.assertIn("net.ipv4.route.foo", aggregate)
        self.assertIn("net.ipv4.conf.foo", aggregate)

    def test_alias_source_matches_merge_dynamic_source_into_doc_name(self) -> None:
        aggregate = {
            "net.ipv4.ip_local_reserved_ports.arp_filter": {
                "name": "net.ipv4.ip_local_reserved_ports.arp_filter",
                "namespace": "net",
                "aliases": {
                    "net.ipv4.ip_local_reserved_ports.arp_filter",
                    "/proc/sys/net/ipv4/ip_local_reserved_ports/arp_filter",
                    "net.ipv4.conf.*.arp_filter",
                    "/proc/sys/net/ipv4/conf/*/arp_filter",
                    "arp_filter",
                },
                "docEntries": [
                    {
                        "name": "net.ipv4.ip_local_reserved_ports.arp_filter",
                        "namespace": "net",
                        "aliases": [
                            "net.ipv4.ip_local_reserved_ports.arp_filter",
                            "/proc/sys/net/ipv4/ip_local_reserved_ports/arp_filter",
                            "net.ipv4.conf.*.arp_filter",
                            "/proc/sys/net/ipv4/conf/*/arp_filter",
                            "arp_filter",
                        ],
                        "doc_path": "Documentation/networking/ip-sysctl.rst",
                        "heading": "arp_filter",
                        "body": "interface-scoped setting",
                        "prefix": "net.ipv4.ip_local_reserved_ports",
                        "kind": "networking-sysctl",
                    }
                ],
                "sourceEntries": [],
            },
            "net.ipv4.conf.*.arp_filter": {
                "name": "net.ipv4.conf.*.arp_filter",
                "namespace": "net",
                "aliases": {
                    "net.ipv4.conf.*.arp_filter",
                    "/proc/sys/net/ipv4/conf/*/arp_filter",
                    "arp_filter",
                },
                "docEntries": [],
                "sourceEntries": [
                    {
                        "name": "net.ipv4.conf.*.arp_filter",
                        "namespace": "net",
                        "aliases": [
                            "net.ipv4.conf.*.arp_filter",
                            "/proc/sys/net/ipv4/conf/*/arp_filter",
                            "arp_filter",
                        ],
                        "source_path": "net/ipv4/devinet.c",
                        "api": "register_net_sysctl",
                        "table": "devinet_sysctl.devinet_vars",
                        "path_segments": ["net", "ipv4", "conf", "*", "arp_filter"],
                        "data_symbol": "ARPFILTER",
                        "handler_symbol": "",
                        "trail": ["arp_filter"],
                    }
                ],
            },
        }

        reconcile_alias_source_matches(aggregate)

        self.assertIn("net.ipv4.ip_local_reserved_ports.arp_filter", aggregate)
        self.assertNotIn("net.ipv4.conf.*.arp_filter", aggregate)
        merged = aggregate["net.ipv4.ip_local_reserved_ports.arp_filter"]
        self.assertEqual(merged["sourceEntries"][0]["name"], "net.ipv4.ip_local_reserved_ports.arp_filter")
        self.assertIn("net.ipv4.conf.*.arp_filter", merged["aliases"])


if __name__ == "__main__":
    unittest.main()
