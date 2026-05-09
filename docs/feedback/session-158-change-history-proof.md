# Session 158 Phase 158-1 — Change-History Reality Check

**Date**: 2026-05-09
**Source**: scripts/session158_phase1_history_check.py

## Purpose

Decide whether v2's current `is_current=TRUE` snapshot is sufficient OR
we need to backfill historical (`is_current=FALSE`) rows from v1 before
DROPing v1. User asked: 'maintain some sense of GEDCOM change over time.'

## 1.1 Resolve candidate gedcom_ids

### Albert Fox
  - gedcom_id=`@I132123840707@` name='Albert ( Elia Ellis ) Fox' birth='abt 1896'/'Minsk, Minsk, Belarus' death='7 Feb 1990'/'Dayton, Montgomery, Ohio, USA' v=5d380adc-bb25-43e0-8950-db883b898f11
  - gedcom_id=`@I132537444180@` name='Albert Isaac ( Aizik ) Fuks Fuchs Fox' birth='5 Nov 1892'/'Minsk, Minsk, Belarus' death='9 Jun 1958'/'Philadelphia, Philadelphia, Pennsylvania, USA' v=5d380adc-bb25-43e0-8950-db883b898f11

### Esther Fox
  (no matches)

### Esther Burd
  - gedcom_id=`@I132126986995@` name='Esther Burd' birth='abt 1900'/'Russia' death='11 Jun 1966'/'Dayton, Montgomery, Ohio, USA' v=5d380adc-bb25-43e0-8950-db883b898f11

### Reva Heft
  - gedcom_id=`@I132127405052@` name='Rebecca ( Reva ) Heft' birth='abt 1865'/'Russia' death='2 Aug 1926'/'Kings, New York, USA' v=5d380adc-bb25-43e0-8950-db883b898f11

### Harry Fox
  - gedcom_id=`@I132128502290@` name='Harry ( Hyman Geshel Lazar ) Fox' birth='13 January 1882'/'Minsk, Minsk, Belarus' death='27 Jul 1979'/'Los Angeles County, California, United States of America' v=5d380adc-bb25-43e0-8950-db883b898f11
  - gedcom_id=`@I132134279291@` name='Harry Abraham Fox' birth='01 Jan 1913'/'New York' death='14 Aug 1954'/'Arverne, New York, USA' v=5d380adc-bb25-43e0-8950-db883b898f11
  - gedcom_id=`@I132332301864@` name='Harry ( Aron Dovid ) Fox' birth='Nov 1876'/'Russia' death='16 Jul 1922'/'New York City, New York, USA' v=5d380adc-bb25-43e0-8950-db883b898f11

## 1.2 Per-person change-history shape (v1)

| Person | gedcom_id | versions | distinct payload_hashes | first→last v |
|---|---|---|---|---|
| Albert Fox | `@I132123840707@` | 9 | 2 | v-1→v9 |
| Esther Burd | `@I132126986995@` | 9 | 2 | v-1→v9 |
| Reva Heft | `@I132127405052@` | 9 | 2 | v-1→v9 |
| Harry Fox | `@I132128502290@` | 9 | 2 | v-1→v9 |

**Deepest history**: Albert Fox with 2 distinct states across 9 versions.

## 1.3 v2 current state for same people

| Person | gedcom_id | v2 row count | distinct payload_hashes |
|---|---|---|---|
| Albert Fox | `@I132123840707@` | 1 | 1 |
| Esther Burd | `@I132126986995@` | 1 | 1 |
| Reva Heft | `@I132127405052@` | 1 | 1 |
| Harry Fox | `@I132128502290@` | 1 | 1 |

## 1.5 Change-history deep dive — Albert Fox (`@I132123840707@`)

| v# | hash[:8] | name | given | surname | birth_date | birth_place | death_date | death_place | current |
|---|---|---|---|---|---|---|---|---|---|
| -1 | `` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 1 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 2 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 3 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 4 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 5 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 6 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 7 | `fd1f05bd` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | False |
| 9 | `1d77bf67` | 'Albert ( Elia Ellis ) Fox' | 'Albert ( Elia Ellis )' | 'Fox' | 'abt 1896' | 'Minsk, Minsk, Belarus' | '7 Feb 1990' | 'Dayton, Montgomery, Ohio, USA' | True |

### v2 current shape for `@I132123840707@`

| first_seen_version | last_seen_version | hash[:8] | name | birth_place | death_place |
|---|---|---|---|---|---|
| 9 | 9 | `1d77bf67` | 'Albert ( Elia Ellis ) Fox' | 'Minsk, Minsk, Belarus' | 'Dayton, Montgomery, Ohio, USA' |

## 1.4 Strategy decision (USER REQUIRED)

**Gap status**: REAL gap exists — multiple states in v1, only current in v2

Options:
- **A. Full historical backfill** (recommended): backfill is_current=FALSE rows to v2 with payload_hash dedup. v2 grows to ~30-50K rows. Native change-history queries.
- **B. Keep v1 alive**: only DROP gedcom_change_log; leave individuals + families. ~300 MB savings instead of ~700 MB. History queries hit v1.
- **C. R2 archive of historical rows**: archive is_current=FALSE to R2; query helper pulls on demand. Full storage win but slow per-id history queries.

## 1.4-decision (recorded retroactively in self-review)

**User chose: Option A** — full historical backfill — via `AskUserQuestion` during Session 158, 2026-05-09. Recorded in `docs/assessments/session-158-assessment.md` and CHANGELOG v0.99.75. Phase 158-2 (the implementation of Option A) was blocked by Supabase pooler instability and rolled to Session 158b. See `HISTORICAL-BACKFILL-REDESIGN-001` in `docs/BACKLOG.md` for the carry-forward.

