"""Raw GEDCOM enrichment helpers.

Keeps python-gedcom for core family extraction, but layers a raw line parser on
top so the full GEDCOM record structure is preserved and accessible.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rhodesli_ml.importers.gedcom_parser import (
    GedcomCitation,
    GedcomEvent,
    GedcomMediaObject,
    GedcomMediaRef,
    GedcomName,
    GedcomNode,
    GedcomRecord,
    GedcomSourceRecord,
)

_LINE_RE = re.compile(
    r"^(?P<level>\d+)\s+(?:(?P<xref>@[^@]+@)\s+)?(?P<tag>[A-Za-z0-9_]+)(?: (?P<value>.*))?$"
)

_INDIVIDUAL_EVENT_TAGS = {
    "BIRT": "birth",
    "DEAT": "death",
    "BURI": "burial",
    "CREM": "cremation",
    "ADOP": "adoption",
    "BAPM": "baptism",
    "CHR": "christening",
    "CONF": "confirmation",
    "NATU": "naturalization",
    "EMIG": "emigration",
    "IMMI": "immigration",
    "CENS": "census",
    "RESI": "residence",
    "OCCU": "occupation",
    "EDUC": "education",
    "GRAD": "graduation",
    "RETI": "retirement",
    "PROB": "probate",
    "WILL": "will",
    "DSCR": "description",
    "FACT": "fact",
    "EVEN": "event",
}

_FAMILY_EVENT_TAGS = {
    "MARR": "marriage",
    "DIV": "divorce",
    "ENGA": "engagement",
    "ANUL": "annulment",
    "MARB": "marriage_banns",
    "MARC": "marriage_contract",
    "MARL": "marriage_license",
    "MARS": "marriage_settlement",
    "EVEN": "event",
    "FACT": "fact",
}

_INDIVIDUAL_STRUCTURAL_TAGS = {
    "NAME",
    "SEX",
    "FAMC",
    "FAMS",
    "SOUR",
    "OBJE",
    "NOTE",
    "CHAN",
    "RIN",
}

_FAMILY_STRUCTURAL_TAGS = {
    "HUSB",
    "WIFE",
    "CHIL",
    "NOTE",
    "SOUR",
    "OBJE",
    "CHAN",
    "RIN",
}


def _parse_gedcom_line(line: str) -> tuple[int, str | None, str, str]:
    match = _LINE_RE.match(line.rstrip("\n"))
    if not match:
        raise ValueError(f"Invalid GEDCOM line: {line.rstrip()}")
    level = int(match.group("level"))
    xref = match.group("xref")
    tag = match.group("tag")
    value = match.group("value") or ""
    return level, xref, tag, value


def _node_to_dict(node: GedcomNode) -> dict:
    return {
        "level": node.level,
        "tag": node.tag,
        "xref_id": node.xref_id,
        "value": node.value,
        "line_number": node.line_number,
        "children": [_node_to_dict(child) for child in node.children],
    }


def _children(node: GedcomNode, tag: str) -> list[GedcomNode]:
    return [child for child in node.children if child.tag == tag]


def _first_child(node: GedcomNode, tag: str) -> GedcomNode | None:
    for child in node.children:
        if child.tag == tag:
            return child
    return None


def _node_text(node: GedcomNode | None, *, strip_result: bool = True) -> str:
    if node is None:
        return ""
    text = node.value or ""
    for child in node.children:
        if child.tag == "CONC":
            text += _node_text(child, strip_result=False)
        elif child.tag == "CONT":
            text += "\n" + _node_text(child, strip_result=False)
    return text.strip() if strip_result else text


def _first_child_text(node: GedcomNode | None, tag: str) -> str:
    return _node_text(_first_child(node, tag)) if node else ""


def _pointer_or_none(value: str | None) -> str | None:
    if value and value.startswith("@") and value.endswith("@"):
        return value
    return None


def parse_raw_records(filepath: str) -> dict[str, GedcomRecord]:
    """Parse a GEDCOM file into top-level raw records with exact raw text."""

    path = Path(filepath)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    records: dict[str, GedcomRecord] = {}

    root: GedcomNode | None = None
    stack: list[GedcomNode] = []
    raw_lines: list[str] = []
    record_index = 0

    def _finalize() -> None:
        nonlocal record_index, root, stack, raw_lines
        if root is None:
            return
        record_index += 1
        record_type = root.tag
        record_key = root.xref_id or f"{record_type}:{record_index}"
        raw_text = "\n".join(raw_lines)
        records[record_key] = GedcomRecord(
            record_key=record_key,
            record_type=record_type,
            root=root,
            raw_text=raw_text,
            record_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            xref_id=root.xref_id,
        )
        root = None
        stack = []
        raw_lines = []

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            level, xref, tag, value = _parse_gedcom_line(line)
        except ValueError:
            if root is None or line.lstrip()[:1].isdigit():
                raise
            raw_lines.append(line)
            _append_invalid_line(stack, line)
            continue
        node = GedcomNode(level=level, tag=tag, value=value, xref_id=xref, line_number=line_number)

        if level == 0:
            _finalize()
            root = node
            stack = [node]
            raw_lines = [line]
            continue

        if root is None:
            raise ValueError(f"Encountered nested GEDCOM line before a root record at line {line_number}")

        raw_lines.append(line)
        while stack and stack[-1].level >= level:
            stack.pop()
        if not stack:
            raise ValueError(f"Malformed GEDCOM nesting at line {line_number}")
        stack[-1].children.append(node)
        stack.append(node)

    _finalize()
    return records


def _extract_notes(nodes: list[GedcomNode]) -> list[str]:
    return [text for text in (_node_text(node) for node in nodes) if text]


def _extract_citation(node: GedcomNode) -> GedcomCitation:
    data_node = _first_child(node, "DATA")
    return GedcomCitation(
        source_xref=_pointer_or_none(node.value),
        page=_first_child_text(node, "PAGE") or None,
        data_text=_first_child_text(data_node, "TEXT") or None,
        data_date=_first_child_text(data_node, "DATE") or None,
        url=_first_child_text(node, "_URL") or _first_child_text(data_node, "WWW") or None,
        apid=_first_child_text(node, "_APID") or None,
        note=_first_child_text(node, "NOTE") or None,
        raw_node=_node_to_dict(node),
    )


def _extract_citations(nodes: list[GedcomNode]) -> list[GedcomCitation]:
    return [_extract_citation(node) for node in nodes]


def _extract_media_ref(node: GedcomNode) -> GedcomMediaRef:
    crop_source = _first_child(node, "_CROP") or node
    crop = {}
    for tag, field in (
        ("_LEFT", "left"),
        ("_TOP", "top"),
        ("_WDTH", "width"),
        ("_HGHT", "height"),
        ("_TYPE", "type"),
    ):
        value = _first_child_text(crop_source, tag)
        if value:
            crop[field] = value
    return GedcomMediaRef(
        object_xref=_pointer_or_none(node.value),
        title=_first_child_text(node, "TITL") or None,
        is_primary=_first_child_text(node, "_PRIM").upper() == "Y",
        crop=crop,
        raw_node=_node_to_dict(node),
    )


def _extract_media_refs(nodes: list[GedcomNode]) -> list[GedcomMediaRef]:
    return [_extract_media_ref(node) for node in nodes]


def _ordered_non_empty(*values: str | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        ordered.append(value)
        seen.add(value)
    return ordered


def _parse_name_parts(raw_name: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)(?:\s*/(.*?)/)?$", raw_name.strip())
    if not match:
        return raw_name.strip(), ""
    given = (match.group(1) or "").strip()
    surname = (match.group(2) or "").strip()
    return given, surname


def _display_name(raw_name: str, given_name: str, surname: str) -> str:
    name_parts = [part for part in (given_name.strip(), surname.strip()) if part]
    if name_parts:
        return " ".join(name_parts)
    return raw_name.strip()


def _append_invalid_line(stack: list[GedcomNode], line: str) -> None:
    """Fold malformed content lines into the current GEDCOM node value."""

    current = stack[-1]
    if current.value:
        current.value = f"{current.value}\n{line}"
    else:
        current.value = line


def _extract_name_entries(nodes: list[GedcomNode]) -> list[GedcomName]:
    names = []
    for index, node in enumerate(nodes):
        raw_value = _node_text(node)
        parsed_given, parsed_surname = _parse_name_parts(raw_value)
        given_name = _first_child_text(node, "GIVN") or parsed_given
        surname = _first_child_text(node, "SURN") or parsed_surname
        names.append(
            GedcomName(
                full_name=_display_name(raw_value, given_name, surname),
                given_name=given_name,
                surname=surname,
                prefix=_first_child_text(node, "NPFX") or None,
                suffix=_first_child_text(node, "NSFX") or None,
                nickname=_first_child_text(node, "NICK") or None,
                is_primary=index == 0,
                notes=_extract_notes(_children(node, "NOTE")),
                citations=_extract_citations(_children(node, "SOUR")),
                media_refs=_extract_media_refs(_children(node, "OBJE")),
                raw_value=raw_value,
                raw_node=_node_to_dict(node),
            )
        )
    return names


def _extract_custom_tags(nodes: list[GedcomNode], known_tags: set[str]) -> dict[str, list[dict]]:
    custom: dict[str, list[dict]] = {}
    for node in nodes:
        if node.tag in known_tags:
            continue
        custom.setdefault(node.tag, []).append(_node_to_dict(node))
    return custom


def _event_from_node(node: GedcomNode, event_type: str, parse_date_fn) -> GedcomEvent:
    raw_date = _first_child_text(node, "DATE")
    return GedcomEvent(
        event_type=event_type,
        date=parse_date_fn(raw_date) if raw_date else None,
        place=_first_child_text(node, "PLAC") or None,
        raw_date=raw_date,
        value=_node_text(node) or None,
        type_label=_first_child_text(node, "TYPE") or None,
        notes=_extract_notes(_children(node, "NOTE")),
        citations=_extract_citations(_children(node, "SOUR")),
        media_refs=_extract_media_refs(_children(node, "OBJE")),
        raw_tag=node.tag,
        raw_node=_node_to_dict(node),
    )


def _extract_source_record(record: GedcomRecord) -> GedcomSourceRecord:
    root = record.root
    data_node = _first_child(root, "DATA")
    return GedcomSourceRecord(
        xref_id=record.xref_id or record.record_key,
        title=_first_child_text(root, "TITL") or None,
        author=_first_child_text(root, "AUTH") or None,
        publication=_first_child_text(root, "PUBL") or None,
        repository_xref=_pointer_or_none(_first_child_text(root, "REPO")),
        notes=_extract_notes(_children(root, "NOTE")),
        urls=_ordered_non_empty(
            _first_child_text(root, "_URL"),
            _first_child_text(data_node, "WWW"),
        ),
        raw_record=record,
    )


def _extract_media_object(record: GedcomRecord) -> GedcomMediaObject:
    root = record.root
    file_node = _first_child(root, "FILE")
    return GedcomMediaObject(
        xref_id=record.xref_id or record.record_key,
        file=_node_text(file_node) or None,
        form=_first_child_text(file_node, "FORM") or None,
        title=_first_child_text(file_node, "TITL") or _first_child_text(root, "TITL") or None,
        media_type=_first_child_text(root, "_MTYPE") or None,
        notes=_extract_notes(_children(root, "NOTE")) + _extract_notes(_children(file_node, "NOTE")),
        urls=_ordered_non_empty(_first_child_text(root, "_URL")),
        raw_record=record,
    )


def enrich_parsed_gedcom_from_raw(parsed, filepath: str, parse_date_fn) -> None:
    """Attach raw-record preservation and richer extracted data to ParsedGedcom."""

    records = parse_raw_records(filepath)
    parsed.records = records

    for record in records.values():
        if record.record_type == "INDI" and record.xref_id and record.xref_id in parsed.individuals:
            indi = parsed.individuals[record.xref_id]
            indi.raw_record = record
            indi.names = _extract_name_entries(_children(record.root, "NAME"))
            if indi.names:
                primary = indi.names[0]
                indi.full_name = primary.full_name or indi.full_name
                indi.given_name = primary.given_name or indi.given_name
                indi.surname = primary.surname or indi.surname
            indi.notes = _extract_notes(_children(record.root, "NOTE"))
            indi.citations = _extract_citations(_children(record.root, "SOUR"))
            indi.media_refs = _extract_media_refs(_children(record.root, "OBJE"))

            events = []
            for child in record.root.children:
                if child.tag == "BIRT":
                    indi.birth = _event_from_node(child, "birth", parse_date_fn)
                elif child.tag == "DEAT":
                    indi.death = _event_from_node(child, "death", parse_date_fn)
                elif child.tag in _INDIVIDUAL_EVENT_TAGS and child.tag not in {"BIRT", "DEAT"}:
                    events.append(_event_from_node(child, _INDIVIDUAL_EVENT_TAGS[child.tag], parse_date_fn))

            indi.events = events
            indi.custom_tags = _extract_custom_tags(
                record.root.children,
                _INDIVIDUAL_STRUCTURAL_TAGS | set(_INDIVIDUAL_EVENT_TAGS),
            )

        elif record.record_type == "FAM" and record.xref_id and record.xref_id in parsed.families:
            fam = parsed.families[record.xref_id]
            fam.raw_record = record
            fam.notes = _extract_notes(_children(record.root, "NOTE"))
            fam.citations = _extract_citations(_children(record.root, "SOUR"))
            fam.media_refs = _extract_media_refs(_children(record.root, "OBJE"))

            events = []
            marriage = None
            for child in record.root.children:
                if child.tag in _FAMILY_EVENT_TAGS:
                    event = _event_from_node(child, _FAMILY_EVENT_TAGS[child.tag], parse_date_fn)
                    events.append(event)
                    if child.tag == "MARR" and marriage is None:
                        marriage = event

            fam.events = events
            fam.marriage = marriage or fam.marriage
            fam.custom_tags = _extract_custom_tags(
                record.root.children,
                _FAMILY_STRUCTURAL_TAGS | set(_FAMILY_EVENT_TAGS),
            )

        elif record.record_type == "SOUR" and record.xref_id:
            parsed.sources[record.xref_id] = _extract_source_record(record)
        elif record.record_type == "OBJE" and record.xref_id:
            parsed.media_objects[record.xref_id] = _extract_media_object(record)
