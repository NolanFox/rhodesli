"""GEDCOM entity matching and redirect helpers.

These helpers keep versioned imports non-destructive when upstream GEDCOM
exports rekey or merge records. They are intentionally conservative: a
redirect is emitted only when a removed individual has a strong, unambiguous
match in the new current-state snapshot.
"""

from __future__ import annotations

import re
from typing import Any


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(value: Any) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    return {token for token in normalized.split() if len(token) > 1}


def _extract_year_from_text(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(value))
    if match:
        return int(match.group(1))
    return None


def extract_event_year(event_payload: dict[str, Any] | None, raw_value: Any = None) -> int | None:
    if not event_payload:
        return _extract_year_from_text(raw_value)
    date_payload = event_payload.get("date") or {}
    if date_payload.get("year"):
        return int(date_payload["year"])
    return _extract_year_from_text(event_payload.get("raw_date") or raw_value)


def build_individual_match_profile(payload: dict[str, Any]) -> dict[str, Any]:
    name_variants: set[str] = set()
    given_tokens: set[str] = set()
    surname_tokens: set[str] = set()

    primary_name = payload.get("name") or ""
    if primary_name:
        name_variants.add(_normalize_text(primary_name))

    given_name = payload.get("given_name") or ""
    surname = payload.get("surname") or ""
    if given_name:
        given_tokens |= _tokenize(given_name)
    if surname:
        surname_tokens |= _tokenize(surname)
    if given_name or surname:
        name_variants.add(_normalize_text(f"{given_name} {surname}"))

    for name in payload.get("names_json") or []:
        full_name = name.get("full_name") or ""
        if full_name:
            name_variants.add(_normalize_text(full_name))
        if name.get("given_name"):
            given_tokens |= _tokenize(name["given_name"])
        if name.get("surname"):
            surname_tokens |= _tokenize(name["surname"])
        combined = f"{name.get('given_name') or ''} {name.get('surname') or ''}"
        if combined.strip():
            name_variants.add(_normalize_text(combined))

    name_variants.discard("")

    return {
        "primary_name": _normalize_text(primary_name),
        "name_variants": sorted(name_variants),
        "given_tokens": sorted(given_tokens),
        "surname_tokens": sorted(surname_tokens),
        "gender": (payload.get("gender") or "U").upper(),
        "birth_year": extract_event_year(payload.get("birth_event_json"), payload.get("birth_date")),
        "death_year": extract_event_year(payload.get("death_event_json"), payload.get("death_date")),
        "birth_place": _normalize_text(payload.get("birth_place")),
        "death_place": _normalize_text(payload.get("death_place")),
    }


def score_individual_match(old_payload: dict[str, Any], new_payload: dict[str, Any]) -> dict[str, Any]:
    old_profile = build_individual_match_profile(old_payload)
    new_profile = build_individual_match_profile(new_payload)

    score = 0.0
    reasons: list[str] = []

    old_names = set(old_profile["name_variants"])
    new_names = set(new_profile["name_variants"])
    shared_names = sorted(old_names & new_names)
    old_given = set(old_profile["given_tokens"])
    new_given = set(new_profile["given_tokens"])
    old_surname = set(old_profile["surname_tokens"])
    new_surname = set(new_profile["surname_tokens"])

    if old_profile["primary_name"] and old_profile["primary_name"] == new_profile["primary_name"]:
        score += 0.45
        reasons.append("primary_name_exact")
    elif shared_names:
        score += 0.35
        reasons.append("name_variant_overlap")
    elif old_given & new_given and old_surname & new_surname:
        score += 0.28
        reasons.append("given_and_surname_overlap")
    elif old_surname & new_surname:
        score += 0.15
        reasons.append("surname_overlap")
    else:
        return {
            "score": 0.0,
            "reasons": ["no_name_overlap"],
            "old_profile": old_profile,
            "new_profile": new_profile,
        }

    old_gender = old_profile["gender"]
    new_gender = new_profile["gender"]
    if old_gender != "U" and new_gender != "U":
        if old_gender != new_gender:
            return {
                "score": 0.0,
                "reasons": ["gender_conflict"],
                "old_profile": old_profile,
                "new_profile": new_profile,
            }
        score += 0.08
        reasons.append("gender_match")

    old_birth_year = old_profile["birth_year"]
    new_birth_year = new_profile["birth_year"]
    if old_birth_year and new_birth_year:
        if old_birth_year == new_birth_year:
            score += 0.22
            reasons.append("birth_year_exact")
        elif abs(old_birth_year - new_birth_year) == 1:
            score += 0.12
            reasons.append("birth_year_near")
        else:
            score -= 0.15
            reasons.append("birth_year_conflict")

    old_death_year = old_profile["death_year"]
    new_death_year = new_profile["death_year"]
    if old_death_year and new_death_year:
        if old_death_year == new_death_year:
            score += 0.12
            reasons.append("death_year_exact")
        elif abs(old_death_year - new_death_year) == 1:
            score += 0.06
            reasons.append("death_year_near")
        else:
            score -= 0.08
            reasons.append("death_year_conflict")

    if old_profile["birth_place"] and new_profile["birth_place"]:
        if old_profile["birth_place"] == new_profile["birth_place"]:
            score += 0.10
            reasons.append("birth_place_exact")
        elif _tokenize(old_profile["birth_place"]) & _tokenize(new_profile["birth_place"]):
            score += 0.05
            reasons.append("birth_place_overlap")

    if old_profile["death_place"] and new_profile["death_place"]:
        if old_profile["death_place"] == new_profile["death_place"]:
            score += 0.06
            reasons.append("death_place_exact")
        elif _tokenize(old_profile["death_place"]) & _tokenize(new_profile["death_place"]):
            score += 0.03
            reasons.append("death_place_overlap")

    score = max(score, 0.0)
    return {
        "score": round(score, 4),
        "reasons": reasons,
        "old_profile": old_profile,
        "new_profile": new_profile,
    }


def detect_individual_redirects(
    removed_items: list[dict[str, Any]],
    new_map: dict[str, dict[str, Any]],
    old_map: dict[str, dict[str, Any]] | None = None,
    threshold: float = 0.75,
    min_margin: float = 0.15,
) -> list[dict[str, Any]]:
    old_keys = set(old_map or {})
    proposals: list[dict[str, Any]] = []

    for item in removed_items:
        old_payload = item.get("old_payload") or {}
        old_key = item.get("entity_id") or old_payload.get("gedcom_id")
        if not old_key:
            continue

        candidates: list[dict[str, Any]] = []
        for new_key, new_payload in new_map.items():
            result = score_individual_match(old_payload, new_payload)
            if result["score"] < threshold:
                continue
            candidates.append(
                {
                    "new_key": new_key,
                    "score": result["score"],
                    "reasons": result["reasons"],
                    "old_profile": result["old_profile"],
                    "new_profile": result["new_profile"],
                }
            )

        if not candidates:
            continue

        candidates.sort(key=lambda row: (row["score"], row["new_key"]), reverse=True)
        best = candidates[0]
        second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
        margin = round(best["score"] - second_score, 4)
        if len(candidates) > 1 and margin < min_margin:
            continue

        proposals.append(
            {
                "entity_type": "individual",
                "old_key": old_key,
                "new_key": best["new_key"],
                "old_row_id": old_payload.get("id"),
                "redirect_type": "merge_redirect" if best["new_key"] in old_keys else "rekey_redirect",
                "match_score": best["score"],
                "match_basis": {
                    "reasons": best["reasons"],
                    "margin": margin,
                    "candidate_count": len(candidates),
                    "old_profile": best["old_profile"],
                    "new_profile": best["new_profile"],
                },
            }
        )

    proposals.sort(
        key=lambda row: (
            row["match_score"],
            row["match_basis"]["margin"],
            row["old_key"],
            row["new_key"],
        ),
        reverse=True,
    )

    redirects: list[dict[str, Any]] = []
    used_old: set[str] = set()
    used_new: set[str] = set()
    for proposal in proposals:
        if proposal["old_key"] in used_old or proposal["new_key"] in used_new:
            continue
        redirects.append(proposal)
        used_old.add(proposal["old_key"])
        used_new.add(proposal["new_key"])

    redirects.sort(key=lambda row: row["old_key"])
    return redirects


def resolve_redirect_chain(start_key: str, redirect_map: dict[str, str], max_hops: int = 25) -> str:
    current = start_key
    visited = {current}
    hops = 0
    while current in redirect_map and hops < max_hops:
        candidate = redirect_map[current]
        if not candidate or candidate in visited:
            break
        current = candidate
        visited.add(current)
        hops += 1
    return current
