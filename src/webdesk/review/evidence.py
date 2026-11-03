"""Evidence-status rendering for citations (S7-05).

A citation is a reference to a source. This module only describes the status recorded for it. It
never confirms a citation. No status in this module means "verified", and an upstream value of
"verified" is refused and shown as unknown. Verification would need an authority this module does
not have.

PROVISIONAL VOCABULARY. The source-status vocabulary (OPEN-07) and the confidence vocabulary
(OPEN-08) are not confirmed. Every label below carries its open item, so that a later confirmed
vocabulary replaces the labels in one place and no caller depends on the wording.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

SOURCE_STATUS_OPEN_ITEM = "OPEN-07"
CONFIDENCE_OPEN_ITEM = "OPEN-08"

# Provisional source statuses. "verified" is intentionally absent, see the module docstring.
SOURCE_STATUS_LABELS: dict[str, str] = {
    "stale": "Stale source",
    "revoked": "Source revoked",
    "absent": "Source absent",
    "synthetic": "Synthetic evidence, not client source",
    "unverified": "Unverified citation",
}

# Provisional confidence levels. Confidence describes support for a statement, not verification.
CONFIDENCE_LABELS: dict[str, str] = {
    "supported": "Supported by cited text",
    "uncertain": "Uncertain",
    "unsupported": "Unsupported",
    "unknown": "Unknown",
}

UNKNOWN_SOURCE_LABEL = "Status unknown"
UNKNOWN_CONFIDENCE_LABEL = "Confidence unknown"
NOT_RECORDED = "not recorded"


def _provisional(label: str, open_item: str) -> str:
    return f"{label} [provisional {open_item}]"


def _claims_verification(text: str) -> bool:
    """True when the text, once normalised, contains "verif".

    Normalisation applies NFKC (fullwidth and compatibility forms), drops format and combining
    characters (zero-width spaces, dotted capitals), drops every non-letter (spaces and punctuation
    used to split the word), and folds case. It does not map cross-script look-alikes such as
    Cyrillic letters. That residual is recorded in the decision register.
    """
    decomposed = unicodedata.normalize("NFKC", text).casefold()
    letters = "".join(
        char
        for char in unicodedata.normalize("NFD", decomposed)
        if unicodedata.category(char)[0] == "L"
    )
    return "verif" in letters


@dataclass(frozen=True)
class Citation:
    citation_id: str
    source_ref: str
    source_status: str
    confidence: str
    edition: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if not self.citation_id.strip() or not self.source_ref.strip():
            raise ValueError("a citation needs an identifier and a source reference")
        # Free text is rendered beside the status. Text that reads as a verification claim is
        # refused so that it cannot pose as a status. This is a best-effort guard, see
        # _claims_verification.
        for name, value in (
            ("identifier", self.citation_id),
            ("source reference", self.source_ref),
            ("edition", self.edition),
            ("version", self.version),
        ):
            if value is not None and _claims_verification(value):
                raise ValueError(f"the citation {name} must not contain a verification claim")


@dataclass(frozen=True)
class CitationView:
    citation_id: str
    source_ref: str
    source_label: str
    confidence_label: str
    edition: str
    version: str
    note: str
    verified: bool = field(default=False, init=False)


def render_citation(citation: Citation) -> CitationView:
    source_label, note = _source_label(citation.source_status)
    return CitationView(
        citation_id=citation.citation_id,
        source_ref=citation.source_ref,
        source_label=source_label,
        confidence_label=_confidence_label(citation.confidence),
        edition=citation.edition or NOT_RECORDED,
        version=citation.version or NOT_RECORDED,
        note=note,
    )


def _source_label(status: str) -> tuple[str, str]:
    if status in SOURCE_STATUS_LABELS:
        return _provisional(SOURCE_STATUS_LABELS[status], SOURCE_STATUS_OPEN_ITEM), ""
    note = (
        f"Recorded status {status!r} is not an accepted source status. "
        "The citation is not treated as verified."
    )
    return _provisional(UNKNOWN_SOURCE_LABEL, SOURCE_STATUS_OPEN_ITEM), note


def _confidence_label(confidence: str) -> str:
    if confidence in CONFIDENCE_LABELS:
        return _provisional(CONFIDENCE_LABELS[confidence], CONFIDENCE_OPEN_ITEM)
    return _provisional(UNKNOWN_CONFIDENCE_LABEL, CONFIDENCE_OPEN_ITEM)
