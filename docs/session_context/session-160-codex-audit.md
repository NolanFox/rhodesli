# Session 160 — Codex Audit

**Auditor**: Codex CLI v0.130 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: rhodes-wiki commits 74755b2 + 67cd292 — Session 160 Phases 2-4
**Date**: 2026-05-13
**Invocation**: `codex exec "..." </dev/null` (per ai-tool-audit.md working invocation)

## Audit Result

**0 P0** · **2 P1** · **6 P2** · **4 P3**

The committed `post.json` passes the contract validator. The JS-structured path works end-to-end. Findings are about hardening and correctness, not blocking bugs.

---

## P0 — None

---

## P1 — Fix before next session

### P1-1: build_inbox_from_js_extraction.py reopens path-traversal risk

**File**: `scripts/build_inbox_from_js_extraction.py:330` (write_entry) and CLI `--output` parsing

The new JS builder accepts arbitrary `--output` and writes `post.json` / `extracted.json` / `meta.json` without the inbox-root, slug, or symlink checks already implemented in `extract_fb_post.py` (`_resolve_output_path`, Codex Session 159 P1-2 fix).

**Fix**: Import and reuse `_resolve_output_path` (or factor it into a shared module) in `build_inbox_from_js_extraction.py`. Add `--unsafe-output-dir` flag matching the HTML CLI's behaviour.

### P1-2: raw_html_sha256 doesn't match the bytes of extracted.json

**File**: `scripts/build_inbox_from_js_extraction.py:212`

`raw_html_sha256` hashes `json.dumps(extracted, sort_keys=True)` — a canonicalized re-serialization. But `extracted.json` written to disk at line 291 is `extracted_path.read_text()` — the original bytes. The two differ (`cced...152a` in committed `post.json` vs `398e...fbdb2` byte hash of the on-disk `extracted.json`).

This breaks the audit-trail integrity check the contract relies on.

**Fix**: Hash `extracted_path.read_bytes()` directly. Alternatively, rename the field to `extracted_json_sha256` and document that the JS path uses a different audit fingerprint than the HTML path.

---

## P2 — Fix opportunistically

### P2-A: shallow input validation; output never re-validated

`build_inbox_from_js_extraction.py:62` (`_validate_extracted_input`) checks only required keys. Non-dict roots, non-dict comments/images, bad `depth`, string counters, invalid `download_status` either crash or write contract-invalid JSON. The current file passes by coincidence; the path doesn't guarantee contract-valid output.

**Fix**: After `build_entry()`, run `validate_inbox_entry()` against the result before writing. Fail loudly on validator errors.

### P2-B: tagged_people_in_caption uses fb_path, contract documents fb_profile_url

`build_inbox_from_js_extraction.py:240` passes JS-extracted caption tags through verbatim. Committed `post.json:348` has `{"name": ..., "fb_path": ...}` while the contract documents `fb_profile_url`. Validator misses this shape (no key required).

**Fix**: Normalize to `fb_profile_url` in `build_entry()`. Add a validator check.

### P2-C: expansion_complete hardcoded True

`build_inbox_from_js_extraction.py:248` — always True. Not equivalent to HTML path which derives from `_has_expansion_buttons`. Should derive from `comments_count_claim` vs `comments_count_extracted` plus known nested-reply gaps.

**Fix**: Default to `False` when `comments_count_claim > comments_count_extracted` OR `_session_160_provenance.known_gaps` is non-empty.

### P2-D: missing e2e/negative tests for JS builder

`tests/test_extract_fb_post.py` covers the HTML CLI but there's no equivalent for `build_inbox_from_js_extraction.py`. Need:
- e2e test: feed minimal extracted.json → run build_entry → run validate_inbox_entry → assert clean.
- Negative test: malformed extracted.json → ValueError.
- Hash-byte equivalence test: ensure raw_html_sha256 matches the bytes of extracted.json on disk.
- JS-vs-HTML contract equivalence fixture.

### P2-E: "Aunt and Uncle to us" anchors to speaker, not speaker's family

`scripts/extract_kinship.py:248` — "Rachel and Nathanel Menashe who were Aunt and Uncle to us" is treated as Rachel/Nathanel → aunt_uncle_of → April Merdjan (speaker). But April's wording suggests Rachel+Nathanel are her *husband's* aunt/uncle, not her own. Triple is technically too strong.

**Fix**: Either downgrade to `aunt_uncle_of_speaker_family` (weaker label), or downgrade confidence to `weak`, or add a `via` field.

### P2-F: shared surnames not expanded in paired names

`scripts/extract_kinship.py:243` (`_AUNT_AND_UNCLE` pattern) — "Rachel and Nathanel Menashe" extracts subject "Rachel" (no surname) and "Nathanel Menashe". This weakens variant matching downstream.

**Fix**: When the second name in a paired construction carries a surname, propagate it to the first if the first is bare-given-name.

### P2-G: dossier wording mislabels Renee as Edward's sibling

`sources/2026-04-28_fb-post_2360240064471306.md:45` and `people/menasche/edward.md:41` describe Henry Tarica's list ("Edward, Renee, Simon and Lionel") as siblings including Renee — but Renee was Edward's wife (née Surmany), not his sister. The dossiers acknowledge ambiguity but the wording invites confusion.

**Fix**: Tighten wording. Treat Simon/Lionel as possible brothers; explicitly note Renee is Edward's wife per her Surmany maiden name.

---

## P3 — Backlog or minor

### P3-A: inbox JSON has no audience marker

Commenter names + FB IDs in `inbox/pending/.../post.json` have no `audience`/redaction marker. Publish-time redactor must explicitly scan JSON too.

**Backlog**: rhodes-wiki BACKLOG entry for "inbox JSON privacy-redaction at publish time."

### P3-B: kinship regex name coverage narrow

`scripts/extract_kinship.py:118` — no accents (e.g. José), hyphenated names (Marie-Claire), middle initials (David A. Schwartz), all-caps names, or apostrophes beyond `O'Brien`. Low DoS risk; coverage gap.

**Backlog**: extend `_NAME` regex per surname-corpus growth.

### P3-C: posts/...md raw_html_sha256 placeholder

`posts/2026-04-28_martha-girgenti-menasche-rhodesia-1971.md:34` has `raw_html_sha256: "see inbox/pending/..."` — placeholder string, not a hash.

**Fix (easy)**: Either populate with the actual hash or remove the field (the inbox entry is the canonical source).

### P3-D: rhodesia.md historical imprecision

`places/rhodesia.md:17` — "Northern + Southern Rhodesia ... renamed Zimbabwe" is imprecise. Northern Rhodesia became **Zambia** in 1964; **Southern Rhodesia** became Zimbabwe in 1980. The 1971 Menasche photo is in Southern Rhodesia specifically.

**Fix**: Correct the sentence.

---

## Acted On in Session 160

(See follow-up commit. Logged here per `.claude/rules/ai-tool-audit.md`.)

## Value Assessment

**Tool**: Codex CLI v0.130 (gpt-5.5, xhigh)
**Wall-clock**: ~3 min
**Tokens used**: 201,372
**Value rating**: **STRONG**

Codex caught two real issues we'd have missed:
1. The raw_html_sha256 / extracted.json byte mismatch — invisible without a hash-equivalence test.
2. The path-traversal regression — re-introduced by oversight (Session 159 had fixed it for the HTML path).

Plus 6 P2 quality issues we'd have caught eventually, but saved time. Would not have found these via Claude self-review alone.
