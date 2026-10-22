"""Prompt-injection defences for retrieved text (M1 S2).

Retrieved text is data. It is never executed as an instruction. Before any passage is used as
evidence, the text is normalized for screening (Unicode compatibility form, format characters
removed, common Cyrillic and Greek lookalikes mapped to Latin, case folded, whitespace collapsed).
A source whose normalized text matches an instruction-like pattern is quarantined as a whole, so a
phrase split across lines or passages cannot slip through.

This is a heuristic. It reduces risk and does not prove that text is safe. Known limits: only a
small confusables table, and only the listed phrasings.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Final

from webdesk.evidence.retrieval import Passage
from webdesk.evidence.sources import SourceRecord

_CONFUSABLES: Final[dict[int, str]] = {
    ord("а"): "a",
    ord("е"): "e",
    ord("о"): "o",
    ord("р"): "p",
    ord("с"): "c",
    ord("у"): "y",
    ord("х"): "x",
    ord("і"): "i",
    ord("ј"): "j",
    ord("ο"): "o",
    ord("α"): "a",
}

_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "instruction_override": re.compile(
        r"ignore (all |any |the )?(previous|prior|above) instructions"
    ),
    "forget_instructions": re.compile(r"forget (your|all|the|previous) (instructions|rules)"),
    "role_marker": re.compile(r"\b(system|assistant|developer) ?:"),
    "policy_override": re.compile(r"disregard .{0,60}(polic|rule|instruction|guardrail)"),
    "secret_request": re.compile(
        r"(reveal|print|send) .{0,40}(system prompt|api key|credentials|secret)"
    ),
}


def _screening_variants(text: str) -> tuple[str, str]:
    # Format characters are screened two ways: removed (so "ign​ore" matches) and replaced by
    # a space (so "previous‍instructions" matches). Either form matching is a flag.
    decomposed = unicodedata.normalize("NFKC", text)

    def finish(value: str) -> str:
        return re.sub(r"\s+", " ", value.translate(_CONFUSABLES).casefold())

    removed = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Cf")
    spaced = "".join(" " if unicodedata.category(ch) == "Cf" else ch for ch in decomposed)
    return finish(removed), finish(spaced)


def normalize_for_screening(text: str) -> str:
    return _screening_variants(text)[1]


def flag_instruction_like(text: str) -> tuple[str, ...]:
    variants = _screening_variants(text)
    return tuple(
        name
        for name, pattern in _PATTERNS.items()
        if any(pattern.search(variant) for variant in variants)
    )


def split_by_trust(
    passages: Iterable[Passage],
) -> tuple[tuple[Passage, ...], tuple[Passage, ...]]:
    usable: list[Passage] = []
    quarantined: list[Passage] = []
    flagged_sources: dict[str, bool] = {}
    for passage in passages:
        source = passage.source
        if source.source_id not in flagged_sources:
            flagged_sources[source.source_id] = _source_is_flagged(source)
        if flagged_sources[source.source_id] or flag_instruction_like(passage.text):
            quarantined.append(passage)
        else:
            usable.append(passage)
    return tuple(usable), tuple(quarantined)


def _source_is_flagged(source: SourceRecord) -> bool:
    return bool(flag_instruction_like(source.text))
