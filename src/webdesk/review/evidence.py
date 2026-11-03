"""Evidence-status rendering for citations (S7-05).

A citation carries two approved fields and one provisional field:

- evidence_status: the AI evidence vocabulary (Sprint 6 register OPEN-07, contract section 10.4).
  This module accepts unverified, not_applicable and conflicting. The values verified and
  partially_verified are set only by a human Foundation workflow (contract section 10.4), which
  this module does not implement, so they are refused. An adapter value "cited" maps to unverified.
- check_outcome: SUPPORTED, UNSUPPORTED or UNKNOWN (Sprint 6 register OPEN-08, contract 10.2).
  It defaults to UNKNOWN, as the contract does.
- source_condition: stale, revoked, absent or synthetic. This is a provisional marker from the
  S7-05 requirement. It is not an approved vocabulary and is labelled as such.

A citation is never shown as verified. Free text (identifier, source reference, edition, version) is
guarded against verification claims (see _claims_verification). The guard is best effort: it folds
the Latin look-alikes listed below, and it does not map cross-script look-alikes such as Cyrillic
letters. The status fields do not depend on it, because they come from closed vocabularies.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from webdesk.review.textutil import clean_key, clean_text, exact, is_blank

# The AI evidence vocabulary (OPEN-07). verified and partially_verified are human-only (10.4).
EVIDENCE_STATUSES = frozenset({"unverified", "not_applicable", "conflicting"})
HUMAN_ONLY_EVIDENCE_STATUSES = frozenset({"verified", "partially_verified"})
# Adapter evidence values map to the AI vocabulary through this table only (OPEN-07).
ADAPTER_EVIDENCE_MAP: dict[str, str] = {"cited": "unverified", "unverified": "unverified"}

# The check outcome vocabulary (OPEN-08). UNKNOWN is the default when neither of the others holds.
CHECK_OUTCOMES = frozenset({"SUPPORTED", "UNSUPPORTED", "UNKNOWN"})

# Provisional source conditions from the S7-05 requirement. Not an approved vocabulary.
SOURCE_CONDITIONS = frozenset({"stale", "revoked", "absent", "synthetic"})

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
    when the whole word is the status label "unverified", which is a recorded status and not an
    assertion. A hyphen or space inside it ("Un-verified") is not the label and is refused.
    "verification" is a noun and is not matched. Cross-script look-alikes are not mapped (R5), and
    visual look-alikes outside the fold table are not caught (R7).
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


def ai_status_from_adapter(status: str) -> str:
    """Map an adapter evidence value to the AI vocabulary (OPEN-07 table). Others are refused."""
    if type(status) is not str or status not in ADAPTER_EVIDENCE_MAP:
        raise ValueError("an adapter evidence value outside the mapping table is refused")
    return ADAPTER_EVIDENCE_MAP[status]


@dataclass(frozen=True)
class Citation:
    citation_id: str
    source_ref: str
    evidence_status: str
    check_outcome: str = "UNKNOWN"
    source_condition: str | None = None
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
        if (
            type(self.evidence_status) is str
            and self.evidence_status in HUMAN_ONLY_EVIDENCE_STATUSES
        ):
            raise ValueError(
                "verified and partially_verified are set only by a human Foundation workflow; "
                "a citation is never verified in this module"
            )
        if type(self.evidence_status) is not str or self.evidence_status not in EVIDENCE_STATUSES:
            raise ValueError("the evidence status must be one of the AI evidence statuses")
        if type(self.check_outcome) is not str or self.check_outcome not in CHECK_OUTCOMES:
            raise ValueError("the check outcome must be SUPPORTED, UNSUPPORTED or UNKNOWN")
        if self.source_condition is not None and (
            type(self.source_condition) is not str or self.source_condition not in SOURCE_CONDITIONS
        ):
            raise ValueError("the source condition must be stale, revoked, absent or synthetic")
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
    evidence_label: str
    check_label: str
    condition_label: str
    edition: str
    version: str
    verified: bool = field(default=False, init=False)


def render_citation(citation: Citation) -> CitationView:
    citation = exact(citation, Citation, "a citation view is built from a Citation")
    condition = (
        ""
        if citation.source_condition is None
        else (
            f"Source condition: {citation.source_condition} "
            "(provisional marker; not an approved vocabulary). "
        )
    )
    return CitationView(
        citation_id=citation.citation_id,
        source_ref=citation.source_ref,
        evidence_label=f"Evidence status: {citation.evidence_status} (OPEN-07 mapping)",
        check_label=f"Check outcome: {citation.check_outcome} (OPEN-08)",
        condition_label=condition,
        edition=citation.edition or NOT_RECORDED,
        version=citation.version or NOT_RECORDED,
    )
