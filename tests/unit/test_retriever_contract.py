"""The in-memory retriever must pass the contract any future production retriever must also pass."""

from __future__ import annotations

from tests.support.retriever_contract import check_retriever_contract
from webdesk.evidence.retrieval import InMemoryRetriever


def test_in_memory_retriever_satisfies_the_retrieval_contract() -> None:
    check_retriever_contract(InMemoryRetriever)
