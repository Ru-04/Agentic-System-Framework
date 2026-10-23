"""AI-S02 H-1 regression: a statement that reorders or rewords its quote is refused.

The independent reviewer showed that "sync not must the store orders." was accepted for the quote
"The store must not sync orders." by a token-subset check, because every word appears in the quote.
An exact bounded span refuses it, since the words are not in the quote's order.

Revert-check: with the statement check replaced by the earlier token-subset rule, the parametrised
reorder tests below fail. This was run on a scratch copy of the tree (see the handoff note).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_engine.contracts.semantic import (
    IntakeItem,
    IntakeKind,
    SemanticCategory,
    SemanticProposal,
    statement_is_traced,
    statement_span,
)

QUOTE = "The store must not sync orders."
SEG = "SEG-SYN-0001-A"


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param("sync not must the store orders.", id="reviewer-example"),
        pytest.param("The store must sync not orders.", id="swap-not-and-sync"),
        pytest.param("orders sync must not store the.", id="reversed"),
        pytest.param("store The must not sync orders.", id="first-two-swapped"),
        pytest.param("not must The store sync orders.", id="scrambled-head"),
    ],
)
def test_reordered_statement_is_not_an_exact_span(statement: str) -> None:
    assert statement_span(statement, QUOTE) is None
    assert not statement_is_traced(statement, QUOTE)


@pytest.mark.parametrize("statement", ["sync not must the store orders.", "orders sync must not"])
def test_reordered_statement_is_refused_as_an_intake_summary(statement: str) -> None:
    with pytest.raises(ValidationError, match="not an exact span"):
        IntakeItem(
            item_key="INT-001",
            segment_id=SEG,
            quote=QUOTE,
            kind=IntakeKind.REQUIREMENT_CANDIDATE,
            summary=statement,
        )


def test_reordered_statement_is_refused_as_a_proposal() -> None:
    with pytest.raises(ValidationError, match="not an exact span"):
        SemanticProposal(
            proposal_key="SEM-001",
            segment_id=SEG,
            quote=QUOTE,
            category=SemanticCategory.FUNCTIONAL,
            normalized_statement="sync not must the store orders.",
        )


def test_in_order_sub_span_is_still_accepted() -> None:
    # Control: the exact-span rule keeps legitimate in-order spans.
    assert statement_is_traced("must not sync orders", QUOTE)
    start = QUOTE.index("must not sync orders")
    assert statement_span("must not sync orders", QUOTE) == (start, start + 20)
