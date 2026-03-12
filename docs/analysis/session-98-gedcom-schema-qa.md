# Session 98 GEDCOM Schema Q&A

**Date:** 2026-03-11  
**Purpose:** Preserve the key user questions from Session 98 and the resulting design answers so future GEDCOM and multi-tree work can build on explicit reasoning instead of oral history.

## Q1. Is the importer brittle because it required many retries?

**Question:** Repeated retries and long runtime looked like a warning sign. Was the system fundamentally brittle?

**Answer:** The original runtime path had real production-scale failure modes:
- REST batch writes could disconnect under heavy staged imports.
- direct DB finalize initially failed on UUID handling and large current-row swaps.
- the importer materialized the entire change log in memory, which inflated RAM and slowed the tail of the run.

The core data model was not the problem. The operational import path was. Session 98 hardened that path by:
- keeping writes append-only until final current-state activation
- separating staging from current-row activation
- using direct DB writes for large entity batches
- making the current-state swap transaction-safe
- streaming change-log writes in bounded batches
- preserving failed versions as audit history instead of mutating live current rows

## Q2. How could a small GEDCOM file expand to gigabytes of memory?

**Question:** How can a GEDCOM export that is only a few megabytes produce a multi-gigabyte working set?

**Answer:** The GEDCOM file is compact source text. The importer expands it into:
- parsed Python objects for every person, family, event, source, media object, and raw record
- normalized old/new snapshot maps for diffing
- change-log entries for every field-level difference
- JSON payloads and serialized values for DB writes

The March 11 import produced `370,366` change-log entries. Python object overhead plus duplicated string/dict structures turned a small text file into a much larger in-memory working set. Session 98 now streams change-log writes instead of accumulating that entire structure first.

## Q3. Does the current model distinguish a new GEDCOM tree from an update to an existing tree?

**Question:** Is the schema robust enough to tell apart a new GEDCOM versus an update to an existing one?

**Answer:** For a single tree, yes:
- `gedcom_versions` gives version lineage
- `source_hash` prevents duplicate successful imports
- current-state rows are versioned and append-only

For multiple independent trees, not fully yet. The next schema phase needs:
- explicit tree/source manifests separate from `community_id`
- source-tree lineage distinct from canonical person identity
- support for multiple tree inputs and non-GEDCOM sources without pretending they are all one version chain

## Q4. Does the model preserve identity when names change, facts change, or IDs merge?

**Question:** If a name changes but the GEDCOM ID stays the same, or if Ancestry merges/rekeys people, do we preserve continuity?

**Answer:** Yes for stable source IDs, and now structurally yes for rekeys/merges:
- stable GEDCOM IDs become versioned modifications with field-level diffs
- removed/rekeyed IDs can be recorded in `gedcom_entity_redirects`
- face links are resolved through redirect lineage instead of destructive rewrites

Important constraint:
- redirect detection is conservative on purpose
- ambiguous cases should remain `removed + added` rather than inventing a bad merge

Session 98 additionally hardened bootstrap behavior so the first versioned import can emit redirects too, not only later version-to-version imports.

## Q5. After seven runs, are we confident and what is still outstanding?

**Question:** After seven runs, are we actually done and what remains?

**Answer:** For the current single-tree rich GEDCOM mirror, confidence is high:
- the live March 11 import is applied as GEDCOM version `7`
- all existing `gedcom_face_links` resolve against current GEDCOM individuals
- live data stayed non-destructive during failed attempts
- app, ML, and fast CI verification all passed on the integrated tree

Still outstanding at the architecture level:
- explicit multi-tree manifests
- cross-community person projection rules
- canonical person/relationship/claim layer above source mirrors
- promotion logic for chat-derived facts and ML-derived facts

## Q6. How should trees that span multiple communities work?

**Question:** A single tree may span Fox and Rhodesli today, and future trees may span multiple communities or contain people present in more than one community.

**Answer:** The next schema phase should separate:
- source tree identity
- canonical person identity
- community visibility/projection

Recommended model:
- a GEDCOM tree is a source artifact, not owned by one community
- a person can appear in multiple communities
- communities decide visibility and UX framing, not source ownership
- source records link into canonical people through provenance-bearing mappings

This avoids duplicating source trees per community and handles people like Roland Fox cleanly.

## Q7. Why is Melanie Strauss's family tree a useful future test case?

**Question:** Melanie Strauss's family will likely come through a separate GEDCOM and separate photo collection.

**Answer:** It is the right real-world forcing function for the next schema phase because it combines:
- a separate source tree
- possible overlap by marriage/family links
- potentially distinct community presentation
- the need for one canonical person graph across multiple families and communities

Future work should validate the multi-tree design against that case explicitly rather than treating it as a hypothetical edge case.

## Q8. Did the live Session 98 import leave any broken GEDCOM links?

**Question:** Were any existing face-to-GEDCOM links broken by the live bootstrap import?

**Answer:** No. Direct SQL verification after the applied import showed:
- `67` `gedcom_face_links` rows with a GEDCOM id
- `21,944` current GEDCOM individuals
- `0` unresolved face links against current GEDCOM individuals

`gedcom_entity_redirects` is currently empty in production because no live linked GEDCOM id required redirect repair after the bootstrap import. The importer was still patched so future first-time bootstraps can emit redirect lineage when needed.
