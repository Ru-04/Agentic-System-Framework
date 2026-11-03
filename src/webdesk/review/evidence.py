"""Evidence-status rendering for citations (S7-05).

A citation is a reference to a source. This module only describes the status recorded for it. It
never confirms a citation. No status in this module means "verified", and an upstream value of
"verified" is shown as unknown. Verification would need an authority this module does not have.

PROVISIONAL VOCABULARY. The source-status vocabulary (OPEN-07) and the confidence vocabulary
(OPEN-08) are not confirmed. Every label below carries its open item, so that a later confirmed
vocabulary replaces the labels in one place and no caller depends on the wording.

Free text (identifier, source reference, edition, version) is shown beside the status. A word in
that text that claims verification is refused (see _claims_verification). The guard is best effort:
it folds the Latin look-alikes listed below, and it does not map cross-script look-alikes such as
Cyrillic letters. The status path does not depend on it, because status values come from a closed
vocabulary and are refused at construction otherwise.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from webdesk.review.textutil import clean_key, clean_text, exact, is_blank

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


# The stems that assert a result: verified, verify, verifies, verifying, verifier, verifiable,
# verifiably, verifiability.
# "verification" and "verifications" are nouns in source names and are not matched.
_CLAIM_STEM = re.compile(r"verif(?:ied|ies|ying|iab|ier|y)")
_LETTER_RUN = re.compile(r"[^\W\d_]+")
_STATUS_WORD = "unverified"


def _claims_verification(text: str) -> bool:
    """True when the text contains a claim of verification, after normalisation.

    Normalisation applies NFKC, folds the Latin look-alikes listed above, removes combining and
    format characters, and folds case. The letters of consecutive words are then joined, so a claim
    split by a space, hyphen or stray punctuation ("Veri fied", "Not-Verified") is still found, and
    a claim inside a longer word ("Notverified", "Reverified") is found too. A match is not a claim
    when it lies wholly inside the status label "unverified", which is a recorded status and not an
    assertion. "verification" is a noun and is not matched. Cross-script look-alikes are not mapped
    (R5), and visual look-alikes outside the fold table are not caught (R7).
    """
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_SAME_SCRIPT_FOLDS)
    stripped = "".join(
        char
        for char in unicodedata.normalize("NFD", folded)
        if unicodedata.category(char) not in ("Mn", "Cf")
    )
    words = _LETTER_RUN.findall(stripped)
    joined = "".join(words)
    starts: list[int] = []
    offset = 0
    for word in words:
        starts.append(offset)
        offset += len(word)
    for match in _CLAIM_STEM.finditer(joined):
        index = _word_index(starts, match.start())
        word = words[index]
        inside_status_label = word == _STATUS_WORD and match.end() <= starts[index] + len(word)
        if not inside_status_label:
            return True
    return False


def _word_index(starts: list[int], position: int) -> int:
    index = 0
    for candidate, start in enumerate(starts):
        if start <= position:
            index = candidate
        else:
            break
    return index


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
        # The status and confidence come from the closed vocabularies. Anything else is refused, so
        # a free-text status can never be shown beside the real status (QA 6, D-1 and D-2).
        if type(self.source_status) is not str or self.source_status not in SOURCE_STATUS_LABELS:
            raise ValueError(
                "the source status must be one of the recorded source statuses; "
                "a citation is never recorded as verified"
            )
        if type(self.confidence) is not str or self.confidence not in CONFIDENCE_LABELS:
            raise ValueError("the confidence must be one of the recorded confidence levels")
        for name in ("edition", "version"):
            value = getattr(self, name)
            if value is None or is_blank(value):
                # An empty (or invisible-only) edition or version means none was recorded.
                object.__setattr__(self, name, None)
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
