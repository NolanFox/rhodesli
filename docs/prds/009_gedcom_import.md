# PRD: GEDCOM Import

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Stub
**Session:** TBD (planned Session 33)

---

## Problem Statement

Family members have genealogical data in GEDCOM files (the standard format for family tree software). Importing this data would enrich identity records with birth/death/marriage dates, locations, and family relationships — transforming Rhodesli from a photo archive into a connected family history tool.

## Who This Is For

- **Family members**: Import their family tree data to enrich the archive
- **Admin**: Cross-reference photo identities with genealogical records
- **Researchers**: Access structured demographic data about the Rhodes community

## Key Requirements

- Parse GEDCOM 5.5/7.0 files for individuals, families, events
- Extract dates (birth, death, marriage), locations, relationships
- Match GEDCOM individuals to existing identities (name matching)
- Support multiple GEDCOM uploads from different family branches
- Preview before import — show what will be added/matched

## Dependencies

- BE-010 (structured identity names) — DONE
- BE-014 (surname variants) — DONE
- Identity metadata system — DONE
