"""Regression tests for rich GEDCOM preservation."""

from pathlib import Path

from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.importers.gedcom_rich import parse_raw_records


RICH_GEDCOM = """0 HEAD
1 SOUR TEST
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Leon /Capeluto/
2 GIVN Leon
2 SURN Capeluto
1 NAME Big Leon /Capeluto/
2 TYPE aka
2 NICK Big Leon
2 NOTE Preferred in family letters
1 SEX M
1 BIRT
2 DATE 12 MAR 1903
2 PLAC Rhodes, Ottoman Empire
2 SOUR @S1@
3 PAGE Birth ledger p. 14
3 DATA
4 DATE 13 MAR 1903
4 TEXT Certified copy
4 WWW https://example.com/birth
3 _APID 1,2::3
2 NOTE Born at home
2 OBJE @M1@
3 _PRIM Y
3 _CROP
4 _LEFT 10
4 _TOP 20
4 _WDTH 30
4 _HGHT 40
1 EVEN Right before moving up to Asheville
2 TYPE migration_note
2 PLAC Asheville, North Carolina, USA
2 NOTE Family oral history
1 NOTE First line
2 CONT Second line
2 CONC  continued
1 SOUR @S1@
2 PAGE Person summary
2 DATA
3 TEXT Household interview
3 WWW https://example.com/person
2 _APID 9,9::9
1 OBJE @M1@
2 TITL Portrait
2 _PRIM Y
0 @I2@ INDI
1 NAME Victoria /Capuano/
2 GIVN Victoria
2 SURN Capuano
1 SEX F
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 MARR
2 DATE 1 JAN 1935
2 PLAC New York, USA
2 SOUR @S1@
3 PAGE Marriage cert
2 OBJE @M1@
3 _PRIM Y
1 DIV
2 DATE 1940
1 NOTE Family note
1 SOUR @S1@
2 PAGE Family summary
0 @S1@ SOUR
1 TITL Birth Record
1 AUTH Civil Registry
1 PUBL Rhodes Archive
1 _URL https://example.com/source
1 DATA
2 WWW https://example.com/source-data
1 NOTE Source note
0 @M1@ OBJE
1 FILE photo.jpg
2 FORM jpg
2 TITL Leon portrait
1 TITL Portrait object
1 _MTYPE photo
1 _URL https://example.com/media
1 NOTE Media note
0 TRLR
"""


def _write_gedcom(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(content)
    return path


class TestGedcomRichPreservation:
    def test_preserves_names_notes_citations_and_media(self, tmp_path):
        path = _write_gedcom(tmp_path, "rich.ged", RICH_GEDCOM)

        parsed = parse_gedcom(str(path))
        indi = parsed.individuals["@I1@"]

        assert indi.full_name == "Leon Capeluto"
        assert indi.raw_record is not None
        assert len(indi.names) == 2
        assert indi.names[0].full_name == "Leon Capeluto"
        assert indi.names[1].full_name == "Big Leon Capeluto"
        assert indi.names[1].raw_value == "Big Leon /Capeluto/"
        assert indi.names[1].nickname == "Big Leon"
        assert indi.names[1].notes == ["Preferred in family letters"]

        assert indi.notes == ["First line\nSecond line continued"]
        assert len(indi.citations) == 1
        assert indi.citations[0].page == "Person summary"
        assert indi.citations[0].data_text == "Household interview"
        assert indi.citations[0].url == "https://example.com/person"
        assert indi.citations[0].apid == "9,9::9"

        assert len(indi.media_refs) == 1
        assert indi.media_refs[0].object_xref == "@M1@"
        assert indi.media_refs[0].title == "Portrait"
        assert indi.media_refs[0].is_primary is True

        assert indi.birth is not None
        assert indi.birth.date is not None
        assert indi.birth.date.year == 1903
        assert indi.birth.citations[0].page == "Birth ledger p. 14"
        assert indi.birth.citations[0].data_text == "Certified copy"
        assert indi.birth.citations[0].url == "https://example.com/birth"
        assert indi.birth.media_refs[0].crop == {
            "left": "10",
            "top": "20",
            "width": "30",
            "height": "40",
        }

        assert len(indi.events) == 1
        assert indi.events[0].event_type == "event"
        assert indi.events[0].value == "Right before moving up to Asheville"
        assert indi.events[0].type_label == "migration_note"
        assert indi.events[0].place == "Asheville, North Carolina, USA"
        assert indi.events[0].notes == ["Family oral history"]

    def test_preserves_family_source_and_media_records(self, tmp_path):
        path = _write_gedcom(tmp_path, "rich.ged", RICH_GEDCOM)

        parsed = parse_gedcom(str(path))
        fam = parsed.families["@F1@"]
        source = parsed.sources["@S1@"]
        media = parsed.media_objects["@M1@"]

        assert fam.raw_record is not None
        assert [event.event_type for event in fam.events] == ["marriage", "divorce"]
        assert fam.marriage is not None
        assert fam.marriage.citations[0].page == "Marriage cert"
        assert fam.marriage.media_refs[0].object_xref == "@M1@"
        assert fam.notes == ["Family note"]
        assert fam.citations[0].page == "Family summary"

        assert source.raw_record is not None
        assert source.title == "Birth Record"
        assert source.author == "Civil Registry"
        assert source.publication == "Rhodes Archive"
        assert source.urls == ["https://example.com/source", "https://example.com/source-data"]
        assert source.notes == ["Source note"]

        assert media.raw_record is not None
        assert media.file == "photo.jpg"
        assert media.form == "jpg"
        assert media.title == "Leon portrait"
        assert media.media_type == "photo"
        assert media.urls == ["https://example.com/media"]
        assert media.notes == ["Media note"]

    def test_tolerates_embedded_non_structural_lines(self, tmp_path):
        content = """0 HEAD
1 SOUR TEST
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Test /Person/
1 NOTE <line>Alpha
</line><line>Beta
2 CONC  Gamma
0 TRLR
"""
        path = _write_gedcom(tmp_path, "malformed.ged", content)

        records = parse_raw_records(str(path))
        record = records["@I1@"]

        assert "</line><line>Beta" in record.raw_text
        note = next(child for child in record.root.children if child.tag == "NOTE")
        assert note.value == "<line>Alpha\n</line><line>Beta"
        assert note.children[0].tag == "CONC"
        assert note.children[0].value == " Gamma"

