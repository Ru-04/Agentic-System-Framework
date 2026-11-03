"""Evidence-status rendering for citations (S7-05).

A citation is a reference to a source. This module only describes the status recorded for it. It
never confirms a citation. No status in this module means "verified", and an upstream value of
"verified" is shown as unknown. Verification would need an authority this module does not have.

PROVISIONAL VOCABULARY. The source-status vocabulary (OPEN-07) and the confidence vocabulary
(OPEN-08) are not confirmed. Every label below carries its open item, so that a later confirmed
vocabulary replaces the labels in one place and no caller depends on the wording.

Free text (identifier, source reference, edition, version) is shown beside the status. Text that
reads as a verification claim is refused. The guard is best effort: it folds the Latin look-alikes
listed below, and it does not map cross-script look-alikes such as Cyrillic letters. The status
path does not depend on it, because status values come from a closed vocabulary.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from webdesk.review.textutil import clean_key, clean_text, exact

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

# Latin letters that look like other Latin letters once a diacritic or stroke is dropped. This is
# a list of the same-script look-alikes found in QA, not a complete table of Latin look-alikes.
_SAME_SCRIPT_FOLDS = str.maketrans(
    {
        "ı": "i",  # dotless i
        "İ": "i",  # dotted capital I
        "ſ": "s",  # long s
        "ƒ": "f",  # f with hook
        "ɪ": "i",  # small capital I
        "ɡ": "g",  # script g
        "ɑ": "a",  # alpha
        "ɩ": "i",  # iota
        "ɨ": "i",  # i with stroke
    }
)


def _provisional(label: str, open_item: str) -> str:
    return f"{label} [provisional {open_item}]"


def _claims_verification(text: str) -> bool:
    """True when the text, once normalised, contains "verif".

    Normalisation applies NFKC (fullwidth and compatibility forms), folds the Latin look-alikes
    above, drops format and combining characters (zero-width spaces, dotted capitals), drops every
    non-letter (spaces and punctuation used to split the word), and folds case.
    """
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_SAME_SCRIPT_FOLDS)
    letters = "".join(
        char
        for char in unicodedata.normalize("NFD", folded)
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
        object.__setattr__(
            self, "citation_id", clean_key(self.citation_id, "a citation needs an identifier")
        )
        object.__setattr__(
            self,
            "source_ref",
            clean_key(self.source_ref, "a citation needs a source reference"),
        )
        for name in ("edition", "version"):
            value = getattr(self, name)
            if value is None:
                continue
            object.__setattr__(self, name, clean_text(value, f"the citation {name} must be text"))
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
    citation = exact(citation, Citation, "a citation view is built from a Citation")
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


def _source_label(status: object) -> tuple[str, str]:
    if type(status) is str and status in SOURCE_STATUS_LABELS:
        return _provisional(SOURCE_STATUS_LABELS[status], SOURCE_STATUS_OPEN_ITEM), ""
    note = (
        f"Recorded status {status!r} is not an accepted source status. "
        "The citation is not treated as verified."
    )
    return _provisional(UNKNOWN_SOURCE_LABEL, SOURCE_STATUS_OPEN_ITEM), note


def _confidence_label(confidence: object) -> str:
    if type(confidence) is str and confidence in CONFIDENCE_LABELS:
        return _provisional(CONFIDENCE_LABELS[confidence], CONFIDENCE_OPEN_ITEM)
    return _provisional(UNKNOWN_CONFIDENCE_LABEL, CONFIDENCE_OPEN_ITEM)
