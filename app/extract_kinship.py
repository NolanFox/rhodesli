"""Kinship-relationship extractor — Session 160 PERSON-MATCH-001 / Phase 3.

COPIED FROM rhodes-wiki Session 160 in rhodesli Session 161 (2026-05-13)
to decouple cross-repo Python imports per Codex pre-execution audit P1-7.
The canonical source remains `/Users/nolanfox/rhodes-wiki/scripts/extract_kinship.py`;
rhodesli copy should be re-synced when rhodes-wiki bumps the extractor's
behaviour (e.g. when new kinship patterns are added). rhodesli depends on
the JSON contract output, NOT on the rhodes-wiki Python module.

Comments in Rhodes-Sephardi FB posts encode dense genealogical signal. Example
from session-160 capture (Martha Girgenti's post about Edward & Renee Menasche):

    "Rachel and Nathanel Menashe who were Aunt and Uncle to us.
     Rachel being the sister of my Mother-in-law Diana Amato Merdjan."

That single sentence states:
  - Rachel and Nathanel Menashe are married (paired phrasing)
  - They are aunt+uncle to the commenter's husband
  - Rachel is the sister of Diana Amato Merdjan
  - Diana Amato Merdjan is the commenter's mother-in-law

This module surfaces relationship triples (subject, relation, object) from
free-form English text using regex patterns tuned to the Rhodes-Sephardi FB
discourse style we observed. spaCy/NER is over-engineering for v1 — the
patterns we need are narrow and well-attested in the corpus.

Output shape:

    [
      {
        "subject": "Sarah Surmany",
        "relation": "mother_of",
        "object": "Renee",
        "evidence": "Renee with her wonderful Mother \"Madam Sarah Surmany\"",
        "comment_id": "2360919741070005",
        "confidence": "good",
      },
      ...
    ]

Where `relation` is one of the canonical relation labels in `RELATION_LABELS`.
Confidence:
  - "strong"  = direct kinship phrase ("X is the mother of Y")
  - "good"    = possessive form ("X's mother Y")
  - "possible" = implication ("X and Y" with same surname, married pairing)
  - "weak"    = same-comment proximity only

This is purposefully conservative — emit a possible relationship rather than
miss one. Admin review (rhodes-wiki person.md frontmatter) is the source of
truth, NOT this extractor's output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# Canonical relation labels. Use these strings in `relation` field; downstream
# tools (dossier writer, rhodesli cross-ref) key off them.
RELATION_LABELS = frozenset({
    "spouse_of",          # X married Y (symmetric)
    "parent_of",          # X is parent of Y
    "mother_of",          # X is mother of Y (more specific than parent_of)
    "father_of",
    "child_of",
    "sibling_of",         # X is sibling of Y
    "sister_of",
    "brother_of",
    "aunt_uncle_of",      # X is aunt/uncle of Y
    "niece_nephew_of",
    "cousin_of",
    "in_law_of",          # generic in-law relationship
    "mother_in_law_of",
    "father_in_law_of",
    "friend_of",
    "relative_of",        # ambiguous "relatives" — admin must refine
    "knew",               # weak: "I knew the family"
})


@dataclass(frozen=True)
class KinshipTriple:
    subject: str          # name as written in source
    relation: str         # one of RELATION_LABELS
    object: str           # name as written in source
    evidence: str         # verbatim source snippet
    comment_id: str | None  # source comment_id (or None for caption)
    confidence: str       # "strong" | "good" | "possible" | "weak"

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
            "evidence": self.evidence,
            "comment_id": self.comment_id,
            "confidence": self.confidence,
        }


# Helper: cleanup a captured name. Strip quotes, honorifics, possessives.
_HONORIFICS = re.compile(r"^(Madam|Mr|Mrs|Ms|Dr|Mme|Mlle|Sr|Sra|Don|Rabbi)\.?\s+", re.IGNORECASE)
_TRAILING_PUNCT = re.compile(r"[\"',.;:!?\s]+$")
_LEADING_PUNCT = re.compile(r"^[\"',.;:!?\s]+")


def _clean_name(name: str) -> str:
    if not name:
        return ""
    name = _LEADING_PUNCT.sub("", name)
    name = _TRAILING_PUNCT.sub("", name)
    name = _HONORIFICS.sub("", name)
    return name.strip()


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Names: 1-4 capitalized words (allows "Diana Amato Merdjan" or single "Camillo").
# Allow internal quotes for "Madam Sarah Surmany". Wrapped in (?-i:...) so the
# regex enforces case sensitivity for NAMES even when the surrounding pattern
# uses re.IGNORECASE for kinship vocabulary.
_NAME = r'(?-i:"?(?:[A-Z][a-z\']+\s+){0,3}[A-Z][a-z\']+"?)'

# "X being the [sister/brother/etc] of Y"
_BEING_OF = re.compile(
    rf'({_NAME})\s+being\s+(?:the\s+)?(sister|brother|mother|father|aunt|uncle|wife|husband|cousin|niece|nephew|son|daughter|spouse)\s+of\s+(?:(?:my|his|her|their|our)\s+(?:Mother-in-law|Father-in-law|Brother-in-law|Sister-in-law)\s+)?({_NAME})',
    re.IGNORECASE
)

# "X is/was the [relation] of Y"
_IS_OF = re.compile(
    rf'({_NAME})\s+(?:is|was)\s+(?:the\s+|my\s+|his\s+|her\s+|their\s+|our\s+)?(sister|brother|mother|father|aunt|uncle|wife|husband|cousin|niece|nephew|son|daughter|spouse|mother-in-law|father-in-law)\s+(?:of|to)\s+({_NAME})',
    re.IGNORECASE
)

# "X's [relation] Y" (possessive form)
# E.g. "Renee with her wonderful Mother \"Madam Sarah Surmany\""
_POSSESSIVE = re.compile(
    rf"({_NAME})\s+(?:with|and)\s+(?:her|his|their)\s+(?:wonderful\s+|dear\s+)?(Mother|Father|Sister|Brother|Aunt|Uncle|Wife|Husband|Cousin|Son|Daughter)\s+({_NAME})",
    re.IGNORECASE
)

# "X and Y were Aunt and Uncle to us/me" (paired aunt+uncle)
_AUNT_AND_UNCLE = re.compile(
    rf"({_NAME})\s+and\s+({_NAME})\s+(?:who\s+)?(?:were|are)\s+Aunt\s+and\s+Uncle\s+to\s+(?:us|me|him|her|them)",
    re.IGNORECASE
)

# "my/his/her [relation] X" -- e.g. "my Mother-in-law Diana Amato Merdjan"
_MY_RELATION = re.compile(
    r"(?:my|his|her|their|our)\s+(Mother-in-law|Father-in-law|Sister-in-law|Brother-in-law|Mother|Father|Sister|Brother|Aunt|Uncle|Wife|Husband|Cousin|Son|Daughter|Spouse)\s+"
    + rf"({_NAME})",
    re.IGNORECASE
)

# "cousin Y" or "cousin X Y" -- e.g. "thanks so much cousin Martha Girgenti"
_COUSIN_OF_SPEAKER = re.compile(
    rf"\bcousin\s+({_NAME})",
    re.IGNORECASE
)

# Map regex-captured kinship word → canonical RELATION_LABELS value
_RELATION_MAP = {
    "sister": "sister_of",
    "brother": "brother_of",
    "mother": "mother_of",
    "father": "father_of",
    "aunt": "aunt_uncle_of",
    "uncle": "aunt_uncle_of",
    "wife": "spouse_of",
    "husband": "spouse_of",
    "spouse": "spouse_of",
    "cousin": "cousin_of",
    "niece": "niece_nephew_of",
    "nephew": "niece_nephew_of",
    "son": "child_of",
    "daughter": "child_of",
    "mother-in-law": "mother_in_law_of",
    "father-in-law": "father_in_law_of",
    "sister-in-law": "in_law_of",
    "brother-in-law": "in_law_of",
}


def _canonical_relation(word: str) -> str:
    return _RELATION_MAP.get(word.lower(), "relative_of")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_kinship_from_text(
    text: str,
    *,
    speaker_name: str | None = None,
    comment_id: str | None = None,
) -> list[KinshipTriple]:
    """Extract kinship triples from one block of text (caption or comment).

    Args:
        text: free-form English text
        speaker_name: name of the comment author. Used to anchor "my X" patterns
            (e.g. "my Mother-in-law Diana" → Diana is mother_in_law_of speaker).
        comment_id: FB comment_id for provenance; pass None for caption-derived.

    Returns:
        Deduplicated list of KinshipTriple (by (subject_clean, relation, object_clean)).
    """
    if not text:
        return []

    out: dict[tuple[str, str, str], KinshipTriple] = {}

    def add(subj: str, rel: str, obj: str, evidence: str, conf: str) -> None:
        s = _clean_name(subj)
        o = _clean_name(obj)
        if not s or not o or s == o:
            return
        if rel not in RELATION_LABELS:
            return
        key = (s.lower(), rel, o.lower())
        if key in out:
            return
        out[key] = KinshipTriple(s, rel, o, evidence.strip(), comment_id, conf)

    # Pattern 1: "X being the [rel] of Y"
    for m in _BEING_OF.finditer(text):
        subj, rel_word, obj = m.group(1), m.group(2), m.group(3)
        rel = _canonical_relation(rel_word)
        add(subj, rel, obj, m.group(0), "strong")

    # Pattern 2: "X is/was the [rel] of Y"
    for m in _IS_OF.finditer(text):
        subj, rel_word, obj = m.group(1), m.group(2), m.group(3)
        rel = _canonical_relation(rel_word)
        add(subj, rel, obj, m.group(0), "strong")

    # Pattern 3: "X with her wonderful Mother Y"  → Y is mother_of X
    for m in _POSSESSIVE.finditer(text):
        owner, rel_word, target = m.group(1), m.group(2), m.group(3)
        rel = _canonical_relation(rel_word)
        # Possessive: TARGET has relation TO owner. e.g. "Renee with her Mother Sarah" → Sarah mother_of Renee.
        add(target, rel, owner, m.group(0), "good")

    # Pattern 4: "X and Y were Aunt and Uncle to us"
    for m in _AUNT_AND_UNCLE.finditer(text):
        x, y = m.group(1), m.group(2)
        # Codex 160 P2-F: if one name in the pair has a surname (e.g.
        # "Rachel and Nathanel Menashe"), propagate it to the bare-given-name
        # half so downstream matching gets the full identifier. Detect:
        # x = "Rachel", y = "Nathanel Menashe" → x_expanded = "Rachel Menashe".
        x_clean = _clean_name(x)
        y_clean = _clean_name(y)
        x_parts = x_clean.split()
        y_parts = y_clean.split()
        if len(x_parts) == 1 and len(y_parts) >= 2:
            # x is bare given name; y has surname → propagate
            x_expanded = f"{x_parts[0]} {y_parts[-1]}"
            x = x_expanded
        elif len(y_parts) == 1 and len(x_parts) >= 2:
            y_expanded = f"{y_parts[0]} {x_parts[-1]}"
            y = y_expanded
        # X and Y are spouses (paired) AND aunt/uncle to speaker's family
        add(x, "spouse_of", y, m.group(0), "good")
        add(y, "spouse_of", x, m.group(0), "good")
        # Codex 160 P2-E: "to us" is plural — usually means speaker's family
        # (siblings, in-laws), not the speaker individually. Downgrade
        # confidence to "weak" since we can't determine exact relation.
        if speaker_name:
            add(x, "aunt_uncle_of", speaker_name, m.group(0), "weak")
            add(y, "aunt_uncle_of", speaker_name, m.group(0), "weak")

    # Pattern 5: "my Mother-in-law Diana Amato Merdjan"
    for m in _MY_RELATION.finditer(text):
        rel_word, name = m.group(1), m.group(2)
        rel = _canonical_relation(rel_word)
        if speaker_name:
            add(name, rel, speaker_name, m.group(0), "good")

    # Pattern 6: "cousin X" or "thanks cousin X"
    for m in _COUSIN_OF_SPEAKER.finditer(text):
        name = m.group(1)
        if speaker_name:
            add(name, "cousin_of", speaker_name, m.group(0), "good")

    return sorted(out.values(), key=lambda t: (t.subject.lower(), t.relation, t.object.lower()))


def extract_kinship_from_post(post_json: dict) -> list[KinshipTriple]:
    """Run kinship extraction across an entire post.json (caption + all comments).

    Args:
        post_json: a post.json dict (output of build_inbox_from_js_extraction
            or extract_fb_post). Must have `caption`, `comments`, `post_author`.

    Returns:
        Aggregated list of KinshipTriple from caption + all comments.
    """
    triples: list[KinshipTriple] = []

    # Caption: speaker is the post author
    post_author = (post_json.get("post_author") or {}).get("name")
    caption_text = (post_json.get("caption") or {}).get("text", "")
    triples.extend(extract_kinship_from_text(
        caption_text,
        speaker_name=post_author,
        comment_id=None,
    ))

    # Each comment: speaker is the commenter
    for c in post_json.get("comments", []):
        speaker = (c.get("author") or {}).get("name") if isinstance(c.get("author"), dict) else None
        triples.extend(extract_kinship_from_text(
            c.get("text", ""),
            speaker_name=speaker,
            comment_id=c.get("comment_id"),
        ))

    # Final dedupe across caption + comments
    seen: set[tuple[str, str, str]] = set()
    deduped: list[KinshipTriple] = []
    for t in triples:
        key = (t.subject.lower(), t.relation, t.object.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


# ---------------------------------------------------------------------------
# Surname corpus seed (Rhodes-Sephardi heritage names)
# ---------------------------------------------------------------------------
# Used downstream by PERSON-MATCH-001 to score name candidates. Surnames here
# are KNOWN Rhodes-Sephardi heritage surnames; matching one is +1 signal that
# the candidate is a community member rather than a noise word.
RHODES_SEPHARDI_SURNAMES = frozenset({
    # observed in session-160 capture
    "menasche", "menashe", "surmany", "amato", "merdjan", "capelouto",
    "tarica", "girgenti", "amoils", "hanan", "cohen", "hanan cohen",
    # from existing rhodesli collections (Vida/Betty/Nace Capeluto)
    "capeluto", "notrica",
    # other well-attested Rhodes-Sephardi surnames
    "alhadeff", "habib", "hasson", "mizrachi", "behar", "soriano", "sevy",
    "tarazi", "leon", "modiano", "perahia", "russo", "galimidi",
})


def is_rhodes_sephardi_surname(name_or_surname: str) -> bool:
    """Best-effort check: does the surname (last word) match a known Rhodes-Sephardi family?"""
    parts = (name_or_surname or "").strip().split()
    if not parts:
        return False
    surname = parts[-1].lower()
    # Also check the FULL string for double-barreled surnames like "Hanan Cohen"
    full = " ".join(parts).lower()
    return surname in RHODES_SEPHARDI_SURNAMES or full in RHODES_SEPHARDI_SURNAMES
