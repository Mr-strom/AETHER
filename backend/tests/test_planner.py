"""Unit tests for backend/services/retrieve/planner.py"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.services.retrieve.planner import QueryPlan, QueryPlannerService


def test_plan_query_empty_string() -> None:
    planner = QueryPlannerService()
    plan = asyncio.run(planner.plan_query(""))
    assert plan.primary_modality == "text"
    assert plan.sub_queries == []
    assert plan.filters == {}
    assert plan.requires_calculation is False


def test_plan_query_mock_success() -> None:
    planner = QueryPlannerService()
    mock_granite = MagicMock()
    mock_granite.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"primary_modality": "text", "sub_queries": ["voltage level", "panel A-001"], "filters": {"building": "7"}, "requires_calculation": true}'
                }
            }
        ]
    }

    with patch("backend.services.retrieve.planner.model_manager.get", return_value=mock_granite):
        plan = asyncio.run(planner.plan_query("Check voltage level for panel A-001"))

    assert plan.primary_modality == "text"
    assert len(plan.sub_queries) == 2
    assert plan.filters.get("building") == "7"
    assert plan.requires_calculation is True


def test_plan_query_malformed_json_fallback() -> None:
    planner = QueryPlannerService()
    mock_granite = MagicMock()
    mock_granite.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": "NOT VALID JSON"
                }
            }
        ]
    }

    with patch("backend.services.retrieve.planner.model_manager.get", return_value=mock_granite):
        plan = asyncio.run(planner.plan_query("Check status"))

    assert plan.primary_modality == "text"
    assert plan.sub_queries == ["Check status"]
    assert plan.filters == {}
    assert plan.requires_calculation is False
