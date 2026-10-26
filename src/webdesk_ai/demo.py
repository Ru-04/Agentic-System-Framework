"""Synthetic end-to-end demonstration (increment 2).

Covers: a multi-platform brief, a conflicting requirement pair, an unsupported platform, missing
evidence for one topic, a transient model failure followed by a schema-invalid response and a
repair, and a deliberately invalid specialist response in a separate probe run.

Flow: synthetic brief -> ai-read/v1 mock -> orchestrated Requirement Analysis -> authorized
specialist in an isolated process -> validated proposals -> human-review package.

Nothing here approves a requirement, commits an estimate, publishes scope, writes to Foundation,
or calls an external model. Those facts are fixed in the output flags.

Run with: ``uv run python -m webdesk_ai.demo <output.json>``
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from webdesk_ai import synthetic
from webdesk_ai.catalog import default_registry
from webdesk_ai.contracts import EvidenceReference
from webdesk_ai.foundation.client import FoundationReadClient, PrincipalCredential
from webdesk_ai.models import ErrorClass, ScriptedModel
from webdesk_ai.orchestration import ReviewPackage, WorkflowConfig, run_workflow
from webdesk_ai.specialists.base import SpecialistDescriptor, SpecialistRegistry
from webdesk_ai.specialists.doubles import InvalidClaimSpecialist
from webdesk_ai.specialists.shopify import SyntheticShopifyEvidence

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
SYNTHETIC_TOKEN = "synthetic-principal-token-not-a-secret"  # noqa: S105 - synthetic fixture
WITHHELD_TOPIC = "api_integration"
BAD_SCHEMA = '{"requirements": [{"draft_id": "R1"}]}'
SCRIPTED_OUTCOMES: tuple[str | ErrorClass, ...] = (
    ErrorClass.TRANSIENT,
    BAD_SCHEMA,
    synthetic.EXPANDED_ANALYSIS,
)


class _DemoEvidence:
    """Synthetic evidence that withholds one topic, to show the missing-evidence path."""

    def __init__(self) -> None:
        self._inner = SyntheticShopifyEvidence()

    def lookup(self, platform_id: str, topic_keys: Sequence[str]) -> tuple[EvidenceReference, ...]:
        if WITHHELD_TOPIC in topic_keys:
            return ()
        return self._inner.lookup(platform_id, topic_keys)


def _client() -> FoundationReadClient:
    foundation = synthetic.build_expanded_foundation(
        token=SYNTHETIC_TOKEN, now=NOW, expires_at=NOW + timedelta(minutes=15)
    )
    return FoundationReadClient(
        transport=foundation,
        credential=PrincipalCredential(
            token=SYNTHETIC_TOKEN, expires_at=NOW + timedelta(minutes=15)
        ),
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        clock=lambda: NOW,
    )


def _probe_registry() -> SpecialistRegistry:
    base = default_registry()
    shopify = SpecialistDescriptor(
        category_id="shopify_specialist",
        display_name="Shopify Specialist",
        platform_ids=frozenset({"shopify"}),
        factory=InvalidClaimSpecialist,
    )
    others = tuple(d for d in base.descriptors if d.category_id != "shopify_specialist")
    return SpecialistRegistry(version=base.version, descriptors=(shopify, *others))


def _specialist_summary(package: ReviewPackage) -> list[dict[str, Any]]:
    return [
        {
            "category": result.agent_id.split(":", 1)[1],
            "status": result.status.value,
            "errors": list(result.errors),
        }
        for result in package.specialist_results
    ]


def run_demo() -> dict[str, Any]:
    main_model = ScriptedModel(outcomes=SCRIPTED_OUTCOMES)
    main = run_workflow(
        client=_client(),
        config=WorkflowConfig(
            model=main_model,
            registry=default_registry(),
            evidence=_DemoEvidence(),
            authorized_categories=frozenset({"shopify_specialist"}),
            specialist_timeout_seconds=30.0,
        ),
    )
    probe_model = ScriptedModel(outcomes=SCRIPTED_OUTCOMES)
    probe = run_workflow(
        client=_client(),
        config=WorkflowConfig(
            model=probe_model,
            registry=_probe_registry(),
            evidence=SyntheticShopifyEvidence(),
            authorized_categories=frozenset({"shopify_specialist"}),
            specialist_timeout_seconds=30.0,
        ),
    )
    analysis = main.analysis
    return {
        "demonstration": "synthetic",
        "increment": 2,
        "contract": "ai-read/v1",
        "flow": [
            "synthetic multi-platform brief",
            "transient model failure, retried",
            "schema-invalid response, repaired",
            "requirement decomposition with conflicts and overlaps",
            "clarification questions",
            "specialist routing recommendations",
            "authorized specialist in an isolated process",
            "evidence-linked proposed findings",
            "human-review-required package",
        ],
        "model": {
            "provider": main_model.provider_id,
            "transport_attempts": analysis.llm_calls,
            "content_attempts": analysis.content_attempts,
            "rejected_attempts": analysis.rejected_attempts,
            "schema_failures": analysis.schema_failures,
        },
        "main_run": main.model_dump(mode="json"),
        "main_specialists": _specialist_summary(main),
        "invalid_specialist_probe": {
            "model_calls": probe_model.calls,
            "status": probe.status,
            "specialists": _specialist_summary(probe),
            "unsupported_claims_accepted": probe.unsupported_claim_count,
        },
        "flags": main.flags.model_dump(mode="json"),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: python -m webdesk_ai.demo <output.json>\n")
        return 2
    output = run_demo()
    Path(argv[1]).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    analysis = output["main_run"]["analysis"]
    sys.stdout.write(
        f"status={output['main_run']['status']} "
        f"requirements={len(analysis['requirements'])} "
        f"questions={len(analysis['clarification_questions'])} "
        f"content_attempts={output['model']['content_attempts']} "
        f"specialists={[s['status'] for s in output['main_specialists']]} "
        f"probe={[s['status'] for s in output['invalid_specialist_probe']['specialists']]}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
