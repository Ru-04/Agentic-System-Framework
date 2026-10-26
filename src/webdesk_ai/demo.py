"""Synthetic end-to-end demonstration.

Synthetic brief -> Foundation read adapter (mock ai-read/v1) -> Requirement Analysis Agent ->
Shopify Specialist -> evidence-linked proposed findings -> clarification questions ->
human-review-required output.

Nothing here approves scope, commits an estimate, publishes a SOW, writes to Foundation, or calls
an external model. The output records those facts as explicit flags.

Run with: ``uv run python -m webdesk_ai.demo <output.json>``
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from webdesk_ai import synthetic
from webdesk_ai.catalog import default_registry
from webdesk_ai.contracts import SpecialistTask
from webdesk_ai.foundation.client import FoundationReadClient, PrincipalCredential
from webdesk_ai.llm import ScriptedLLM
from webdesk_ai.requirements.agent import RequirementAnalysisAgent
from webdesk_ai.specialists.base import run_specialist
from webdesk_ai.specialists.shopify import SyntheticShopifyEvidence

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
SYNTHETIC_TOKEN = "synthetic-principal-token-not-a-secret"  # noqa: S105
SHOPIFY_CATEGORY = "shopify_specialist"


def run_demo() -> dict[str, Any]:
    foundation = synthetic.build_foundation(
        token=SYNTHETIC_TOKEN, now=NOW, expires_at=NOW + timedelta(minutes=15)
    )
    client = FoundationReadClient(
        transport=foundation,
        credential=PrincipalCredential(
            token=SYNTHETIC_TOKEN, expires_at=NOW + timedelta(minutes=15)
        ),
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        clock=lambda: NOW,
    )
    project = client.get_project()
    run = client.get_run()
    versions = list(client.iter_source_versions(page_limit=2))
    segments = [seg for version in versions for seg in client.iter_segments(version)]

    registry = default_registry()
    llm = ScriptedLLM([synthetic.BAD_ANALYSIS, synthetic.GOOD_ANALYSIS])
    analysis = RequirementAnalysisAgent(llm, registry).analyze(
        run_id=run.run_id, project_id=project.project_id, segments=segments
    )

    shopify_requirements = tuple(
        req for req in analysis.requirements if "shopify" in req.platform_refs
    )
    specialist_output: dict[str, Any] | None = None
    if shopify_requirements:
        task = SpecialistTask(
            task_id="TASK-SHOPIFY-001",
            run_id=run.run_id,
            project_id=project.project_id,
            category_id=SHOPIFY_CATEGORY,
            requirements=shopify_requirements,
            timeout_seconds=10,
        )
        execution = run_specialist(
            registry.instantiate(SHOPIFY_CATEGORY),
            task,
            SyntheticShopifyEvidence(),
            clock=lambda: NOW,
        )
        specialist_output = execution.model_dump(mode="json")

    return {
        "demonstration": "synthetic",
        "contract": "ai-read/v1",
        "flow": [
            "synthetic client brief",
            "Requirement Analysis Agent",
            "atomic requirements",
            "Shopify Specialist",
            "evidence-linked proposed findings",
            "clarification questions",
            "human-review-required output",
        ],
        "foundation_access": {
            "project": project.model_dump(mode="json"),
            "run_status": run.status,
            "source_versions_visible": len(versions),
            "source_versions_in_fixture": len(foundation.versions),
            "segments_read": len(segments),
            "model_attempts": len(llm.prompts),
        },
        "requirement_analysis": analysis.model_dump(mode="json"),
        "specialist": specialist_output,
        "flags": {
            "scope_approved": False,
            "estimate_committed": False,
            "sow_published": False,
            "foundation_writes": 0,
            "external_model_calls": 0,
            "evidence_is_synthetic": True,
            "human_review_required": True,
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: python -m webdesk_ai.demo <output.json>\n")
        return 2
    output = run_demo()
    Path(argv[1]).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    analysis = output["requirement_analysis"]
    sys.stdout.write(
        f"requirements={len(analysis['requirements'])} "
        f"questions={len(analysis['clarification_questions'])} "
        f"status={analysis['status']} specialist={(output['specialist'] or {}).get('status')}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
