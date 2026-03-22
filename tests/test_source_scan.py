import unittest

from tools.extract.source_scan import scan_source_file


SOURCE_SNIPPET = """
static struct ctl_path vm_path[] = {
	{ .procname = "vm" },
	{ }
};

static struct ctl_table vm_table[] = {
	{
		.procname = "numa",
		.child = numa_table,
	},
	{ }
};

static struct ctl_table numa_table[] = {
	{
		.procname = "balancing",
	},
	{ }
};

void register_vm(void)
{
	register_sysctl_paths(vm_path, vm_table);
}
"""

SOURCE_WITH_OLD_TABLE_DECLARATION = """
static ctl_table ipv4_route_table[] = {
	{
		.procname = "min_pmtu",
	},
	{ }
};

static struct ctl_table ipv4_table[] = {
	{
		.procname = "route",
		.child = ipv4_route_table,
	},
	{ }
};

static struct ctl_path ipv4_path[] = {
	{ .procname = "net" },
	{ .procname = "ipv4" },
	{ }
};

void register_ipv4(void)
{
	register_sysctl_paths(ipv4_path, ipv4_table);
}
"""

SOURCE_WITH_TABLE_ALIAS = """
static struct ctl_table ipv4_route_netns_table[] = {
	{
		.procname = "min_pmtu",
		.data = &init_net.ipv4.ip_rt_min_pmtu,
	},
	{ }
};

static int init_route(void)
{
	struct ctl_table *tbl;
	size_t table_size = 2;

	tbl = ipv4_route_netns_table;
	tbl = kmemdup(tbl, sizeof(ipv4_route_netns_table), GFP_KERNEL);

	register_net_sysctl_sz(net, "net/ipv4/route", tbl, table_size);
	return 0;
}
"""

SOURCE_WITH_DYNAMIC_MEMBER_TABLE = """
static struct devinet_sysctl_table {
	struct ctl_table_header *sysctl_header;
	struct ctl_table devinet_vars[4];
} devinet_sysctl = {
	.devinet_vars = {
		DEVINET_SYSCTL_RW_ENTRY(ACCEPT_LOCAL, "accept_local"),
		DEVINET_SYSCTL_RW_ENTRY(RP_FILTER, "rp_filter"),
		DEVINET_SYSCTL_RW_ENTRY(ARPFILTER, "arp_filter"),
		{ }
	},
};

static int __devinet_sysctl_register(struct net *net, char *dev_name)
{
	struct devinet_sysctl_table *t;
	char path[sizeof("net/ipv4/conf/") + IFNAMSIZ];

	t = kmemdup(&devinet_sysctl, sizeof(*t), GFP_KERNEL_ACCOUNT);
	if (!t)
		return -ENOMEM;

	snprintf(path, sizeof(path), "net/ipv4/conf/%s", dev_name);
	t->sysctl_header = register_net_sysctl(net, path, t->devinet_vars);
	return 0;
}
"""


class SourceScanTests(unittest.TestCase):
    def test_nested_tables_expand_to_full_path(self) -> None:
        records = scan_source_file("kernel/sysctl.c", SOURCE_SNIPPET)
        self.assertEqual(records[0].name, "vm.numa.balancing")

    def test_old_style_ctl_table_declarations_are_scanned(self) -> None:
        records = scan_source_file("net/ipv4/route.c", SOURCE_WITH_OLD_TABLE_DECLARATION)
        self.assertEqual(records[0].name, "net.ipv4.route.min_pmtu")

    def test_registration_table_aliases_resolve_to_known_tables(self) -> None:
        records = scan_source_file("net/ipv4/route.c", SOURCE_WITH_TABLE_ALIAS)
        self.assertEqual(records[0].name, "net.ipv4.route.min_pmtu")
        self.assertEqual(records[0].table, "ipv4_route_netns_table")
        self.assertEqual(records[0].data_symbol, "ip_rt_min_pmtu")

    def test_dynamic_member_tables_expand_to_template_paths(self) -> None:
        records = scan_source_file("net/ipv4/devinet.c", SOURCE_WITH_DYNAMIC_MEMBER_TABLE)
        names = {record.name for record in records}
        self.assertIn("net.ipv4.conf.*.accept_local", names)
        self.assertIn("net.ipv4.conf.*.rp_filter", names)
        arp_filter = next(record for record in records if record.name == "net.ipv4.conf.*.arp_filter")
        self.assertEqual(arp_filter.table, "devinet_sysctl.devinet_vars")
        self.assertEqual(arp_filter.path_segments, ["net", "ipv4", "conf", "*", "arp_filter"])


if __name__ == "__main__":
    unittest.main()
