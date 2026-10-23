"""AI-S02 system prompts: fixed text, a valid JSON reply schema, and no client text in them."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from ai_engine.contracts.semantic import IntakeResult, SemanticAnalysisResult
from ai_engine.llm_agents.lead_intake import SYSTEM_PROMPT as INTAKE_PROMPT
from ai_engine.llm_agents.semantic_analysis import SYSTEM_PROMPT as SEMANTIC_PROMPT


@pytest.mark.parametrize(
    "prompt, model",
    [(INTAKE_PROMPT, IntakeResult), (SEMANTIC_PROMPT, SemanticAnalysisResult)],
)
def test_embedded_schema_is_valid_json_matching_the_reply_model(
    prompt: str, model: type[BaseModel]
) -> None:
    schema_text = prompt.split("Schema: ", 1)[1]
    assert json.loads(schema_text) == model.model_json_schema()


@pytest.mark.parametrize("prompt", [INTAKE_PROMPT, SEMANTIC_PROMPT])
def test_prompt_treats_client_text_as_untrusted_data(prompt: str) -> None:
    assert "untrusted data" in prompt
    assert "Do not add any other field" in prompt
