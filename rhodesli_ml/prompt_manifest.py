"""Helpers for prompt-manifest identities and Gemini lineage fields."""

from __future__ import annotations

import hashlib
import json


def _normalize_contract_version(prompt_contract_version: str) -> str:
    value = str(prompt_contract_version)
    if value.startswith("contract"):
        return value
    return f"contract{value}"


def build_prompt_manifest_id(
    prompt_family: str,
    prompt_version: str,
    prompt_variant: str,
    prompt_contract_version: str,
) -> str:
    """Build the canonical compact prompt-manifest identity string."""
    return (
        f"{prompt_family}:{prompt_version}:{prompt_variant}:"
        f"{_normalize_contract_version(prompt_contract_version)}"
    )


def build_prompt_manifest(
    *,
    prompt_family: str,
    prompt_version: str,
    prompt_variant: str,
    prompt_contract_version: str,
    channel: str,
    context_flags: dict | None = None,
    template_source: str = "",
    status: str = "active",
) -> dict:
    """Build the compact prompt-manifest payload logged with Gemini calls."""
    return {
        "prompt_manifest_id": build_prompt_manifest_id(
            prompt_family,
            prompt_version,
            prompt_variant,
            prompt_contract_version,
        ),
        "prompt_family": prompt_family,
        "prompt_version": prompt_version,
        "prompt_variant": prompt_variant,
        "prompt_contract_version": _normalize_contract_version(prompt_contract_version),
        "channel": channel,
        "context_flags": context_flags or {},
        "template_source": template_source,
        "status": status,
    }


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(payload) -> str:
    return _hash_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def build_prompt_lineage_fields(
    manifest: dict,
    *,
    prompt_text: str | None = None,
    full_response=None,
    experiment_id: str | None = None,
    shadow_run_id: str | None = None,
    request_surface: str | None = None,
    request_mode: str | None = None,
    related_state_event_id: str | None = None,
    contract_valid: bool | None = None,
) -> dict:
    """Flatten prompt-manifest data into the fields logged on one API call."""
    fields = {
        "prompt_manifest_id": manifest["prompt_manifest_id"],
        "prompt_family": manifest["prompt_family"],
        "prompt_version": manifest["prompt_version"],
        "prompt_variant": manifest["prompt_variant"],
        "prompt_contract_version": manifest["prompt_contract_version"],
    }

    if prompt_text is not None:
        fields["prompt_hash"] = _hash_text(prompt_text)
    if full_response is not None:
        fields["full_response_hash"] = _hash_json(full_response)
    if experiment_id is not None:
        fields["experiment_id"] = experiment_id
    if shadow_run_id is not None:
        fields["shadow_run_id"] = shadow_run_id
    if request_surface is not None:
        fields["request_surface"] = request_surface
    if request_mode is not None:
        fields["request_mode"] = request_mode
    if related_state_event_id is not None:
        fields["related_state_event_id"] = related_state_event_id
    if contract_valid is not None:
        fields["contract_valid"] = contract_valid

    return fields
