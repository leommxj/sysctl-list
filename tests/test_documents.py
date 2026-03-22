import unittest

from tools.extract.documents import contextual_doc_paths, parse_context_document, parse_document


LEGACY_KERNEL = """
==============================================================

acct:

highwater lowwater frequency

If BSD-style process accounting is enabled these values control
its behaviour.
"""

NETWORKING_RST = """
/proc/sys/net/ipv4/* Variables
==============================

ip_forward - BOOLEAN
	Forward packets between interfaces.

route/max_size - INTEGER
	Maximum number of routes allowed in the kernel.
"""

NET_OVERVIEW = """
1. /proc/sys/net/core - Network core options
============================================

rmem_default
------------

The default setting of the socket receive buffer in bytes.
"""

NETWORKING_CONF_SCOPE = """
/proc/sys/net/ipv4/* Variables
==============================

ip_local_reserved_ports - list of comma separated ranges
	Example path mention: /proc/sys/net/ipv4/ip_local_reserved_ports

``conf/interface/*``
	changes special settings per interface.

accept_local - BOOLEAN
	Accept packets with local source addresses.
"""

NETWORKING_CONF_SCOPE_TXT = """
/proc/sys/net/ipv4/* Variables:

ip_local_reserved_ports - list of comma separated ranges
	Example path mention: /proc/sys/net/ipv4/ip_local_reserved_ports

	conf/interface/*  changes special settings per interface (where
	"interface" is the name of your network interface)

accept_local - BOOLEAN
	Accept packets with local source addresses.
"""

XFS_SYSCTLS = """
sysctls
=======

  fs.xfs.error_level		(Min: 0  Default: 3  Max: 11)
	A volume knob for error reporting when internal errors occur.

  fs.xfs.panic_mask		(Min: 0  Default: 0  Max: 511)
	Causes certain error conditions to call BUG().
"""

LOCKUP_CONTEXT = """
watchdogs
=========

This value may be adjusted via the kernel.watchdog_cpumask sysctl.
For example, echo 0-3 > /proc/sys/kernel/watchdog_cpumask.
"""

RISCV_VECTOR_CONTEXT = """
System runtime configuration
----------------------------

* /proc/sys/abi/riscv_v_default_allow

    Writing the text representation of 0 or 1 to this file sets the default
    system enablement status for new starting userspace programs.

    * 0: Do not allow Vector code to be executed as the default for new processes.
    * 1: Allow Vector code to be executed as the default for new processes.

* Another topic

  Not part of the sysctl entry.
"""


class DocumentParserTests(unittest.TestCase):
    def test_legacy_namespace_parser(self) -> None:
        records = parse_document("Documentation/sysctl/kernel.txt", LEGACY_KERNEL)
        self.assertEqual(records[0].name, "kernel.acct")

    def test_networking_parser_expands_relative_paths(self) -> None:
        records = parse_document("Documentation/networking/ip-sysctl.rst", NETWORKING_RST)
        names = {record.name for record in records}
        self.assertIn("net.ipv4.ip_forward", names)
        self.assertIn("net.ipv4.route.max_size", names)

    def test_net_overview_parser_tracks_section_prefix(self) -> None:
        records = parse_document("Documentation/admin-guide/sysctl/net.rst", NET_OVERVIEW)
        self.assertEqual(records[0].name, "net.core.rmem_default")

    def test_networking_parser_adds_conf_scope_aliases_without_renaming_display_name(self) -> None:
        records = parse_document("Documentation/networking/ip-sysctl.rst", NETWORKING_CONF_SCOPE)
        record = next(item for item in records if item.heading == "accept_local")
        self.assertEqual(record.name, "net.ipv4.ip_local_reserved_ports.accept_local")
        self.assertIn("net.ipv4.conf.*.accept_local", record.aliases)
        self.assertIn("/proc/sys/net/ipv4/conf/*/accept_local", record.aliases)

    def test_networking_txt_parser_adds_conf_scope_aliases_for_legacy_format(self) -> None:
        records = parse_document("Documentation/networking/ip-sysctl.txt", NETWORKING_CONF_SCOPE_TXT)
        record = next(item for item in records if item.heading == "accept_local")
        self.assertEqual(record.name, "net.ipv4.ip_local_reserved_ports.accept_local")
        self.assertIn("net.ipv4.conf.*.accept_local", record.aliases)

    def test_context_parser_extracts_sysctl_section_entries(self) -> None:
        records = parse_context_document(
            "Documentation/admin-guide/xfs.rst",
            XFS_SYSCTLS,
            {"fs.xfs.error_level"},
        )
        self.assertEqual(records[0].name, "fs.xfs.error_level")
        self.assertEqual(records[0].kind, "sysctl-section")

    def test_context_parser_extracts_mentions_from_paragraphs(self) -> None:
        records = parse_context_document(
            "Documentation/admin-guide/lockup-watchdogs.rst",
            LOCKUP_CONTEXT,
            {"kernel.watchdog_cpumask"},
        )
        self.assertEqual(records[0].name, "kernel.watchdog_cpumask")
        self.assertEqual(records[0].kind, "context-mention")

    def test_context_parser_extracts_proc_sys_blocks(self) -> None:
        records = parse_context_document(
            "Documentation/arch/riscv/vector.rst",
            RISCV_VECTOR_CONTEXT,
            {"abi.riscv_v_default_allow"},
        )
        self.assertEqual(records[0].name, "abi.riscv_v_default_allow")
        self.assertEqual(records[0].kind, "context-proc-block")
        self.assertEqual(records[0].heading, "/proc/sys/abi/riscv_v_default_allow")
        self.assertIn("system enablement status", records[0].body)
        self.assertNotIn("Another topic", records[0].body)
        self.assertEqual(records[0].line_start, 5)
        self.assertEqual(records[0].line_end, 11)

    def test_contextual_doc_paths_accepts_any_matched_text_doc(self) -> None:
        paths = [
            "Documentation/arch/riscv/vector.rst",
            "Documentation/admin-guide/sysctl/kernel.rst",
            "Documentation/admin-guide/index.rst",
            "Documentation/devicetree/bindings/foo.yaml",
        ]
        selected = contextual_doc_paths(paths, paths)
        self.assertIn("Documentation/arch/riscv/vector.rst", selected)
        self.assertNotIn("Documentation/admin-guide/sysctl/kernel.rst", selected)
        self.assertNotIn("Documentation/admin-guide/index.rst", selected)
        self.assertNotIn("Documentation/devicetree/bindings/foo.yaml", selected)


if __name__ == "__main__":
    unittest.main()
