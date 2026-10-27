"""AI-S06 orchestration: recommendation, operator confirmation, execution and correlation.

Recommendation is not authorisation. Execution runs only after a verified human operator
confirmation. The workflow is a plain state machine, not LangGraph; see ``workflow.py``.
"""
