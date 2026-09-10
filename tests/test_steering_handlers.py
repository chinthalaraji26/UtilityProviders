"""Unit tests for steering_handlers.py (BudgetWorkflowHandler).

BudgetWorkflowHandler reads prior tool-call results from
self.steering_context.data["ledger"]["tool_calls"], populated in production
by LedgerProvider via agent hooks. For a unit test we can set that dict
directly - steer_before_tool only reads it, so this fully exercises the
guardrail logic without needing a live Agent or model.
"""

import asyncio

from steering_handlers import BudgetWorkflowHandler


def make_ledger(tool_calls):
    return {"ledger": {"tool_calls": tool_calls}}


def lookup_call(tool_name, text):
    return {"tool_name": tool_name, "status": "success", "result": [{"text": text}]}


def run(coro):
    return asyncio.run(coro)


def test_proceeds_for_non_budget_tools():
    handler = BudgetWorkflowHandler()
    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={"name": "find_providers", "input": {}},
    ))
    assert action.type == "proceed"


def test_proceeds_when_no_providers_given():
    handler = BudgetWorkflowHandler()
    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={"name": "estimate_monthly_budget", "input": {}},
    ))
    assert action.type == "proceed"


def test_blocks_when_nothing_has_been_looked_up_yet():
    handler = BudgetWorkflowHandler()
    handler.steering_context.data = make_ledger([])

    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={"name": "estimate_monthly_budget", "input": {"internet_provider": "Google Fiber"}},
    ))
    assert action.type == "guide"
    assert "haven't looked up" in action.reason


def test_blocks_unverified_provider_name():
    handler = BudgetWorkflowHandler()
    handler.steering_context.data = make_ledger([
        lookup_call("find_providers", "Providers serving Austin, TX:\n  Internet:\n    - Spectrum: ~$65.00/mo"),
    ])

    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={"name": "estimate_monthly_budget", "input": {"internet_provider": "Acme Fiber Co"}},
    ))
    assert action.type == "guide"
    assert "Acme Fiber Co" in action.reason


def test_proceeds_when_provider_was_previously_looked_up():
    handler = BudgetWorkflowHandler()
    handler.steering_context.data = make_ledger([
        lookup_call("find_providers", "Providers serving Austin, TX:\n  Internet:\n    - Google Fiber: ~$70.00/mo"),
    ])

    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={"name": "estimate_monthly_budget", "input": {"internet_provider": "Google Fiber"}},
    ))
    assert action.type == "proceed"


def test_proceeds_when_provider_came_from_get_promotions_instead():
    handler = BudgetWorkflowHandler()
    handler.steering_context.data = make_ledger([
        lookup_call("get_promotions", "Google Fiber: $10/mo off for 6 months"),
    ])

    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={"name": "estimate_monthly_budget", "input": {"internet_provider": "Google Fiber"}},
    ))
    assert action.type == "proceed"


def test_checks_all_chosen_providers_not_just_one():
    handler = BudgetWorkflowHandler()
    handler.steering_context.data = make_ledger([
        lookup_call("find_providers", "Internet:\n    - Google Fiber: ~$70.00/mo"),
    ])

    action = run(handler.steer_before_tool(
        agent=None,
        tool_use={
            "name": "estimate_monthly_budget",
            "input": {"internet_provider": "Google Fiber", "electricity_provider": "Acme Power"},
        },
    ))
    assert action.type == "guide"
    assert "Acme Power" in action.reason
