"""Shared paths for the AI Engine test suite. Nothing here reads real client data."""

from __future__ import annotations

from pathlib import Path

AI_ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_ENGINE_ROOT.parent
FIXTURE_PATH = AI_ENGINE_ROOT / "fixtures" / "synthetic_brief_ecommerce.json"
SPEC_REGISTRY_PATH = (
    REPO_ROOT / "WebDesk_Agentic_Requirement_Platform_Specs" / "AGENT_REGISTRY.yaml"
)
