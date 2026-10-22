"""Deterministic rule handlers that stand in for a model in AI-S02 tests. Not product logic.

They read the JSON user payload and answer with fixed keyword rules. Every quote is a verbatim
sentence of its segment, so a correct reply passes traceability. Tests derive broken replies from
the correct one by editing a single field.
"""

from __future__ import annotations

import json
import re
from typing import Any

from conftest import FIXTURE_PATH

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.common import DataClass
from ai_engine.contracts.source import SourceSegment
from ai_engine.llm.port import LLMRequest
from ai_engine.llm_agents.lead_intake import PURPOSE as INTAKE_PURPOSE
from ai_engine.llm_agents.semantic_analysis import PURPOSE as SEMANTIC_PURPOSE

PROJECT_ID = "PRJ-SYN-0001"

_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
_INSTRUCTION_RE = re.compile(
    r"\b(ignore (all |the |any )?(previous|prior|above)|disregard|mark (every|all|each)\b"
    r"|approve (this|the|all) )",
    re.IGNORECASE,
)
_GOAL_RE = re.compile(r"\b(goal|objective|aim)\b", re.IGNORECASE)
_ASSUMPTION_RE = re.compile(r"\bassum\w*\b", re.IGNORECASE)
_CUE_RE = re.compile(
    r"\b(must|should|want|need|needs|support|supports|sync|integrate|update|updates|refreshed|"
    r"comply|feel)\b",
    re.IGNORECASE,
)
_COMPLIANCE_RE = re.compile(r"\b(pci|regulat\w*)\b", re.IGNORECASE)
_INTEGRATION_RE = re.compile(r"\b(sync|integrat\w*|erp|warehouse|refresh\w*)\b", re.IGNORECASE)
_PERFORMANCE_RE = re.compile(r"\b(faster|performance|abandon\w*)\b", re.IGNORECASE)


def load_fixture_segments() -> tuple[str, list[SourceSegment]]:
    """Load the synthetic brief through the mock Foundation adapter, as the other tests do."""
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    segments = adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL)
    return adapter.project_id, list(segments)


def _sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]


def _intake_kind(sentence: str) -> str:
    if _INSTRUCTION_RE.search(sentence):
        return "instruction_like"
    if "?" in sentence:
        return "question"
    if _GOAL_RE.search(sentence):
        return "goal"
    if _ASSUMPTION_RE.search(sentence):
        return "assumption"
    if _CUE_RE.search(sentence):
        return "requirement_candidate"
    return "context"


def _semantic_category(sentence: str) -> str:
    if _COMPLIANCE_RE.search(sentence):
        return "compliance"
    if _INTEGRATION_RE.search(sentence):
        return "integration"
    if _PERFORMANCE_RE.search(sentence):
        return "performance"
    return "functional"


def intake_reply(project_id: str, segments: list[dict[str, str]]) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    unclassified: list[str] = []
    for segment in segments:
        sentences = _sentences(segment["text"])
        if not sentences:
            unclassified.append(segment["segment_id"])
        for sentence in sentences:
            items.append(
                {
                    "item_key": f"INT-{len(items) + 1:03d}",
                    "segment_id": segment["segment_id"],
                    "quote": sentence,
                    "kind": _intake_kind(sentence),
                    "summary": sentence,
                }
            )
    return {
        "project_id": project_id,
        "items": items,
        "unclassified_segment_ids": unclassified,
    }


def semantic_reply(project_id: str, segments: list[dict[str, str]]) -> dict[str, Any]:
    proposals: list[dict[str, str]] = []
    unclassified: list[str] = []
    for segment in segments:
        cited = False
        for sentence in _sentences(segment["text"]):
            if _intake_kind(sentence) != "requirement_candidate":
                continue
            cited = True
            proposals.append(
                {
                    "proposal_key": f"SEM-{len(proposals) + 1:03d}",
                    "segment_id": segment["segment_id"],
                    "quote": sentence,
                    "category": _semantic_category(sentence),
                    "normalized_statement": sentence,
                }
            )
        if not cited:
            unclassified.append(segment["segment_id"])
    return {
        "project_id": project_id,
        "proposals": proposals,
        "unclassified_segment_ids": unclassified,
    }


def rule_reply(request: LLMRequest) -> str:
    """The deterministic 'model': answers either agent from its own JSON payload."""
    payload = json.loads(request.user_payload)
    project_id: str = payload["project_id"]
    segments: list[dict[str, str]] = payload["segments"]
    if request.purpose == INTAKE_PURPOSE:
        return json.dumps(intake_reply(project_id, segments), sort_keys=True)
    if request.purpose == SEMANTIC_PURPOSE:
        return json.dumps(semantic_reply(project_id, segments), sort_keys=True)
    raise ValueError(f"no rule for purpose {request.purpose}")


def reply_dict(request: LLMRequest) -> dict[str, Any]:
    """The correct reply as a mutable dict, for tests that break exactly one field."""
    parsed: dict[str, Any] = json.loads(rule_reply(request))
    return parsed


def as_text(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True)
