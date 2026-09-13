"""Rate-limiter Lambda: the shared counter behind hooks.RateLimiterHook.

Deployed and wired up by scripts/deploy_rate_limiter.py (function name fixed
by hooks.RATE_LIMITER_LAMBDA_NAME). Standalone on purpose - this ships as its
own Lambda deployment package, not part of the agent's own source bundle, so
it has no dependency on strands/bedrock_agentcore/the rest of this repo.

Atomically increments a call count for one (invocation, tool) pair in
DynamoDB and reports whether that count is over the caller's limit. Using
DynamoDB's atomic UpdateItem (rather than read-then-write) is what makes
this correct even if an agent invocation fires several tool calls
concurrently - two concurrent increments can't stomp on each other the way
they could with a plain in-memory dict spread across containers.

Event shape (see hooks.RateLimiterHook._check_via_lambda):
    {"invocation_id": str, "tool_name": str, "max_calls": int}
Returns:
    {"count": int, "blocked": bool}
"""

import os
import time

import boto3

TABLE_NAME = os.environ.get("RATE_LIMIT_TABLE_NAME", "MoversHelperAgentRateLimits")

# How long a counter row lives before DynamoDB's TTL sweeper reclaims it.
# Generous relative to how long one agent turn could plausibly run, so a
# slow turn never sees its own counter vanish mid-turn.
_COUNTER_TTL_SECONDS = 3600

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def handler(event, context=None, table=None):
    """Lambda entrypoint. `table` is for tests only (dependency injection)."""
    invocation_id = event["invocation_id"]
    tool_name = event["tool_name"]
    max_calls = int(event.get("max_calls", 4))

    counter_id = f"{invocation_id}#{tool_name}"
    table = table if table is not None else _get_table()

    response = table.update_item(
        Key={"counter_id": counter_id},
        UpdateExpression=(
            "SET call_count = if_not_exists(call_count, :zero) + :one, "
            "expires_at = :expires_at"
        ),
        ExpressionAttributeValues={
            ":zero": 0,
            ":one": 1,
            ":expires_at": int(time.time()) + _COUNTER_TTL_SECONDS,
        },
        ReturnValues="UPDATED_NEW",
    )
    count = int(response["Attributes"]["call_count"])
    return {"count": count, "blocked": count > max_calls}
