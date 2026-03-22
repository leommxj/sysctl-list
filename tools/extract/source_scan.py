from __future__ import annotations

import re
from dataclasses import dataclass

from .models import SourceRecord

TABLE_PATTERN = re.compile(r"\b(?:const\s+)?(?:struct\s+)?ctl_table\s+([A-Za-z_]\w*)\s*\[\]\s*=\s*\{")
PATH_PATTERN = re.compile(r"\b(?:struct\s+)?ctl_path\s+([A-Za-z_]\w*)\s*\[\]\s*=\s*\{")
INLINE_STRUCT_PATTERN = re.compile(r"\bstruct\s+([A-Za-z_]\w*)\s*\{")
TABLE_ALIAS_LOOKBEHIND = 2400
DYNAMIC_LOOKBEHIND = 16000
IDENTIFIER = r"[A-Za-z_]\w*"
MEMBER_EXPR = rf"{IDENTIFIER}(?:->|\.){IDENTIFIER}"
STRING_LITERAL = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')

REGISTRATION_PATTERNS = [
    ("register_sysctl", re.compile(r"register_sysctl(?:_sz|_init)?\(\s*\"([^\"]+)\"\s*,\s*&?([A-Za-z_]\w*)", re.S)),
    ("register_sysctl_paths", re.compile(r"register_sysctl(?:_table_path|_paths)\(\s*&?([A-Za-z_]\w*)\s*,\s*&?([A-Za-z_]\w*)", re.S)),
    ("register_net_sysctl", re.compile(r"register_net_sysctl(?:_sz|_table|_rotable)?\(\s*[^,]+,\s*\"([^\"]+)\"\s*,\s*&?([A-Za-z_]\w*)", re.S)),
]
DYNAMIC_REGISTRATION_PATTERN = re.compile(r"\b(register_net_sysctl(?:_sz|_table|_rotable)?)\s*\(")


@dataclass(slots=True)
class TableEntry:
    procname: str
    child: str
    data_symbol: str
    handler_symbol: str


def scan_source_file(path: str, text: str) -> list[SourceRecord]:
    table_map = {
        name: parse_ctl_table_array(body)
        for name, body in extract_arrays(text, TABLE_PATTERN).items()
    }
    table_map.update(extract_member_table_arrays(text))
    path_map = {
        name: parse_ctl_path_array(body)
        for name, body in extract_arrays(text, PATH_PATTERN).items()
    }
    records: dict[str, SourceRecord] = {}

    for api, prefix, table in extract_registrations(text, path_map, table_map):
        if table not in table_map:
            continue
        for trail, entry in expand_table(table, table_map, seen=frozenset()):
            if not trail:
                continue
            dotted = normalize_path(prefix + trail)
            records[dotted] = SourceRecord(
                name=dotted,
                namespace=dotted.split(".", 1)[0],
                aliases=sorted({dotted, "/proc/sys/" + dotted.replace(".", "/"), ".".join(trail)}),
                source_path=path,
                api=api,
                table=table,
                path_segments=prefix + trail,
                data_symbol=entry.data_symbol,
                handler_symbol=entry.handler_symbol,
                trail=trail,
            )

    return sorted(records.values(), key=lambda item: item.name)


def extract_arrays(text: str, pattern: re.Pattern[str]) -> dict[str, str]:
    arrays: dict[str, str] = {}
    for match in pattern.finditer(text):
        name = match.group(1)
        brace_index = text.find("{", match.end() - 1)
        if brace_index == -1:
            continue
        body, _ = slice_brace_block(text, brace_index)
        arrays[name] = body
    return arrays


def extract_member_table_arrays(text: str) -> dict[str, list[TableEntry]]:
    arrays: dict[str, list[TableEntry]] = {}
    for match in INLINE_STRUCT_PATTERN.finditer(text):
        brace_index = text.find("{", match.end() - 1)
        if brace_index == -1:
            continue
        struct_body, next_index = slice_brace_block(text, brace_index)
        member_names = re.findall(r"\b(?:const\s+)?(?:struct\s+)?ctl_table\s+([A-Za-z_]\w*)\s*\[", struct_body)
        if not member_names:
            continue
        tail = text[next_index:]
        instance_match = re.match(rf"\s*({IDENTIFIER})\s*=\s*\{{", tail)
        if not instance_match:
            continue
        instance_name = instance_match.group(1)
        init_index = next_index + instance_match.end() - 1
        init_body, _ = slice_brace_block(text, init_index)
        for member_name in member_names:
            member_body = extract_designated_initializer(init_body, member_name)
            if not member_body:
                continue
            entries = parse_ctl_table_array(member_body)
            if entries:
                arrays[f"{instance_name}.{member_name}"] = entries
    return arrays


def extract_designated_initializer(body: str, member_name: str) -> str:
    match = re.search(rf"\.{re.escape(member_name)}\s*=\s*\{{", body)
    if not match:
        return ""
    brace_index = body.find("{", match.end() - 1)
    if brace_index == -1:
        return ""
    member_body, _ = slice_brace_block(body, brace_index)
    return member_body


def parse_ctl_path_array(body: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"\.procname\s*=\s*\"([^\"]+)\"", body)]


def parse_ctl_table_array(body: str) -> list[TableEntry]:
    entries: list[TableEntry] = []
    for chunk in split_top_level_items(body):
        if not chunk:
            continue
        procname_match = re.search(r"\.procname\s*=\s*\"([^\"]+)\"", chunk)
        procname = procname_match.group(1) if procname_match else extract_macro_procname(chunk)
        if not procname:
            continue
        child_match = re.search(r"\.child\s*=\s*&?([A-Za-z_]\w*)", chunk)
        handler_match = re.search(r"\.proc_handler\s*=\s*&?([A-Za-z_]\w*)", chunk)
        entries.append(
            TableEntry(
                procname=procname,
                child=child_match.group(1) if child_match else "",
                data_symbol=extract_data_symbol(chunk),
                handler_symbol=handler_match.group(1) if handler_match else "",
            )
        )
    return entries


def extract_macro_procname(chunk: str) -> str:
    literals = STRING_LITERAL.findall(chunk)
    if not literals:
        return ""
    return literals[-1]


def extract_data_symbol(chunk: str) -> str:
    match = re.search(r"\.data\s*=\s*(?:\([^)]+\)\s*)*([^,\n}]+)", chunk)
    if not match:
        return ""
    tokens = re.findall(r"[A-Za-z_]\w*", match.group(1))
    return tokens[-1] if tokens else ""


def extract_registrations(
    text: str,
    path_map: dict[str, list[str]],
    table_map: dict[str, list[TableEntry]],
) -> list[tuple[str, list[str], str]]:
    registrations: list[tuple[str, list[str], str]] = []
    for api, pattern in REGISTRATION_PATTERNS:
        for match in pattern.finditer(text):
            if api == "register_sysctl_paths":
                path_name, table = match.groups()
                prefix = path_map.get(path_name, [])
            else:
                path_value, table = match.groups()
                prefix = [segment for segment in path_value.strip("/").split("/") if segment]
            table = resolve_table_name(text, match.start(), table, table_map)
            if prefix:
                registrations.append((api, prefix, table))
    registrations.extend(extract_dynamic_registrations(text, table_map))
    return registrations


def resolve_table_name(text: str, position: int, name: str, table_map: dict[str, list[TableEntry]]) -> str:
    if name in table_map:
        return name
    window = text[max(0, position - TABLE_ALIAS_LOOKBEHIND) : position]
    pattern = re.compile(rf"\b{re.escape(name)}\s*=\s*&?([A-Za-z_]\w*)\s*;")
    for match in reversed(list(pattern.finditer(window))):
        candidate = match.group(1)
        if candidate in table_map:
            return candidate
    return name


def extract_dynamic_registrations(
    text: str,
    table_map: dict[str, list[TableEntry]],
) -> list[tuple[str, list[str], str]]:
    registrations: list[tuple[str, list[str], str]] = []
    for match in DYNAMIC_REGISTRATION_PATTERN.finditer(text):
        call_index = text.find("(", match.end() - 1)
        if call_index == -1:
            continue
        args_body, _ = slice_paren_block(text, call_index)
        args = split_top_level_items(args_body)
        if len(args) < 3:
            continue
        path_expr = args[1].strip()
        table_expr = args[2].strip()
        if path_expr.startswith('"'):
            continue
        prefix = resolve_path_expression(text, match.start(), path_expr)
        table_name = resolve_table_expression(text, match.start(), table_expr, table_map)
        if prefix and table_name in table_map:
            registrations.append(("register_net_sysctl", prefix, table_name))
    return registrations


def resolve_path_expression(text: str, position: int, expr: str) -> list[str]:
    value = clean_reference(expr)
    if not re.fullmatch(IDENTIFIER, value):
        return []
    window = text[max(0, position - DYNAMIC_LOOKBEHIND) : position]
    pattern = re.compile(rf"\bsnprintf\(\s*{re.escape(value)}\s*,\s*[^,]+,\s*\"([^\"]+)\"", re.S)
    matches = list(pattern.finditer(window))
    if not matches:
        return []
    template = matches[-1].group(1)
    return template_to_segments(template)


def template_to_segments(template: str) -> list[str]:
    segments: list[str] = []
    for raw_segment in template.strip("/").split("/"):
        value = re.sub(r"%[-+#0-9.*hljztL]*[A-Za-z]", "*", raw_segment).strip()
        if value:
            segments.append(value)
    return segments


def resolve_table_expression(
    text: str,
    position: int,
    expr: str,
    table_map: dict[str, list[TableEntry]],
) -> str:
    value = clean_reference(expr)
    if value in table_map:
        return value
    member_match = re.fullmatch(rf"({IDENTIFIER})(?:->|\.)({IDENTIFIER})", value)
    if member_match:
        base_name, member_name = member_match.groups()
        resolved_base = resolve_symbol_reference(text, position, base_name)
        if resolved_base:
            candidate = f"{resolved_base}.{member_name}"
            if candidate in table_map:
                return candidate
    if re.fullmatch(IDENTIFIER, value):
        resolved = resolve_symbol_reference(text, position, value)
        if resolved and resolved != value:
            return resolve_table_expression(text, position, resolved, table_map)
        return resolve_table_name(text, position, value, table_map)
    return ""


def resolve_symbol_reference(text: str, position: int, name: str, seen: frozenset[str] = frozenset()) -> str:
    if name in seen:
        return name
    window = text[max(0, position - DYNAMIC_LOOKBEHIND) : position]
    patterns = [
        re.compile(rf"\b{re.escape(name)}\s*=\s*kmemdup\(\s*([^,]+)", re.S),
        re.compile(rf"\b{re.escape(name)}\s*=\s*([^;]+);", re.S),
        re.compile(rf"\b{re.escape(name)}\s*\[[^\]]+\]\s*=\s*\"([^\"]+)\"", re.S),
    ]
    for pattern in patterns:
        matches = list(pattern.finditer(window))
        if not matches:
            continue
        rhs = matches[-1].group(1).strip()
        if rhs.startswith('"'):
            return rhs
        reference = clean_reference(rhs)
        if reference.startswith("{"):
            return name
        if not reference or reference == name:
            return name
        if re.fullmatch(MEMBER_EXPR, reference):
            return reference
        if re.fullmatch(IDENTIFIER, reference):
            return resolve_symbol_reference(text, position, reference, seen | {name})
        return reference
    return name


def clean_reference(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^\((?:[^()]+)\)\s*", "", text)
    while text.startswith("&"):
        text = text[1:].strip()
    return text.replace(" ", "")


def expand_table(
    table_name: str,
    table_map: dict[str, list[TableEntry]],
    seen: frozenset[str],
) -> list[tuple[list[str], TableEntry]]:
    if table_name in seen:
        return []
    results: list[tuple[list[str], TableEntry]] = []
    for entry in table_map.get(table_name, []):
        segment = entry.procname.strip("/")
        if not segment:
            continue
        if entry.child and entry.child in table_map:
            child_rows = expand_table(entry.child, table_map, seen | {table_name})
            if child_rows:
                for child, leaf in child_rows:
                    results.append(([segment, *child], leaf))
                continue
        results.append(([segment], entry))
    return results


def normalize_path(segments: list[str]) -> str:
    flattened: list[str] = []
    for segment in segments:
        for item in segment.split("/"):
            value = item.strip()
            if value:
                flattened.append(value)
    return ".".join(flattened)


def split_top_level_items(body: str) -> list[str]:
    items: list[str] = []
    start = 0
    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(body):
        char = body[index]
        next_char = body[index + 1] if index + 1 < len(body) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if in_char:
            if char == "\\":
                index += 2
                continue
            if char == "'":
                in_char = False
            index += 1
            continue
        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "'":
            in_char = True
            index += 1
            continue
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "," and brace_depth == 0 and paren_depth == 0 and bracket_depth == 0:
            item = body[start:index].strip()
            if item:
                items.append(item)
            start = index + 1
        index += 1

    tail = body[start:].strip()
    if tail:
        items.append(tail)
    return items


def slice_paren_block(text: str, start: int) -> tuple[str, int]:
    return slice_delimited_block(text, start, "(", ")")


def slice_brace_block(text: str, start: int) -> tuple[str, int]:
    return slice_delimited_block(text, start, "{", "}")


def slice_delimited_block(text: str, start: int, open_char: str, close_char: str) -> tuple[str, int]:
    depth = 0
    index = start
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if in_char:
            if char == "\\":
                index += 2
                continue
            if char == "'":
                in_char = False
            index += 1
            continue
        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "'":
            in_char = True
            index += 1
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
        index += 1
    return text[start + 1 :], len(text)
