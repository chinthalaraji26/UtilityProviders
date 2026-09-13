"""Unit tests for lambdas/rate_limiter/handler.py.

Uses an in-memory stand-in for the DynamoDB table (injected via the
`table` parameter) instead of moto or a real table - the handler only calls
table.update_item(Key=..., UpdateExpression=..., ExpressionAttributeValues=...)
and reads response["Attributes"]["call_count"], so a small fake that
implements just that contract behaves identically for testing purposes.
"""

from lambdas.rate_limiter.handler import handler


class FakeTable:
    """Emulates just enough of DynamoDB's atomic UpdateItem to test the handler."""

    def __init__(self):
        self.rows: dict[str, int] = {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues, ReturnValues):
        counter_id = Key["counter_id"]
        self.rows[counter_id] = self.rows.get(counter_id, 0) + 1
        return {"Attributes": {"call_count": self.rows[counter_id]}}


def invoke(table, invocation_id: str, tool_name: str, max_calls: int = 4) -> dict:
    event = {"invocation_id": invocation_id, "tool_name": tool_name, "max_calls": max_calls}
    return handler(event, context=None, table=table)


def test_first_call_is_not_blocked():
    table = FakeTable()
    result = invoke(table, "inv-1", "utilify_get_promotions", max_calls=4)
    assert result == {"count": 1, "blocked": False}


def test_blocks_once_count_exceeds_max_calls():
    table = FakeTable()
    for _ in range(2):
        invoke(table, "inv-1", "utilify_get_promotions", max_calls=2)

    result = invoke(table, "inv-1", "utilify_get_promotions", max_calls=2)
    assert result == {"count": 3, "blocked": True}


def test_counts_are_independent_per_invocation():
    table = FakeTable()
    invoke(table, "inv-1", "utilify_get_promotions", max_calls=1)

    # A different invocation_id (different turn/customer) starts its own count,
    # even for the same tool - this is what makes the limit correct across
    # containers instead of shared globally by tool name alone.
    result = invoke(table, "inv-2", "utilify_get_promotions", max_calls=1)
    assert result == {"count": 1, "blocked": False}


def test_counts_are_independent_per_tool_within_one_invocation():
    table = FakeTable()
    invoke(table, "inv-1", "utilify_get_promotions", max_calls=1)

    result = invoke(table, "inv-1", "utilify_search_utility_providers", max_calls=1)
    assert result == {"count": 1, "blocked": False}


def test_defaults_max_calls_to_four_when_omitted():
    table = FakeTable()
    event = {"invocation_id": "inv-1", "tool_name": "utilify_get_promotions"}
    for _ in range(4):
        handler(event, context=None, table=table)

    result = handler(event, context=None, table=table)
    assert result == {"count": 5, "blocked": True}
