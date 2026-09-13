"""Unit tests for hooks.py (RateLimiterHook).

Uses simple duck-typed stand-ins for the hook events instead of the real
Strands event classes - RateLimiterHook only reads event.tool_use["name"]
and sets event.cancel_tool, so a plain object with those attributes behaves
identically for testing purposes.
"""

from types import SimpleNamespace

from hooks import RateLimiterHook


def tool_call_event(name: str) -> SimpleNamespace:
    return SimpleNamespace(tool_use={"name": name}, cancel_tool=None)


def test_allows_calls_up_to_the_limit():
    hook = RateLimiterHook(max_calls=3)
    for _ in range(3):
        event = tool_call_event("utilify_search_utility_providers")
        hook.check(event)
        assert event.cancel_tool is None


def test_blocks_calls_beyond_the_limit():
    hook = RateLimiterHook(max_calls=2)
    for _ in range(2):
        hook.check(tool_call_event("utilify_get_promotions"))

    event = tool_call_event("utilify_get_promotions")
    hook.check(event)
    assert event.cancel_tool is not None
    assert "2-call limit" in event.cancel_tool


def test_blocked_message_names_the_offending_tool():
    hook = RateLimiterHook(max_calls=1)
    hook.check(tool_call_event("utilify_get_promotions"))

    event = tool_call_event("utilify_get_promotions")
    hook.check(event)
    assert "utilify_get_promotions" in event.cancel_tool


def test_stays_blocked_on_further_calls_past_the_limit():
    hook = RateLimiterHook(max_calls=1)
    hook.check(tool_call_event("utilify_get_promotions"))
    hook.check(tool_call_event("utilify_get_promotions"))

    event = tool_call_event("utilify_get_promotions")
    hook.check(event)
    assert event.cancel_tool is not None  # 3rd call still blocked, not just the 2nd


def test_counts_are_tracked_per_tool_independently():
    hook = RateLimiterHook(max_calls=1)
    hook.check(tool_call_event("utilify_search_utility_providers"))

    other_event = tool_call_event("utilify_get_promotions")
    hook.check(other_event)
    assert other_event.cancel_tool is None  # different tool, own count


def test_reset_clears_counts_between_turns():
    hook = RateLimiterHook(max_calls=1)
    hook.check(tool_call_event("utilify_search_utility_providers"))

    hook.reset(event=None)

    event = tool_call_event("utilify_search_utility_providers")
    hook.check(event)
    assert event.cancel_tool is None  # count was reset, so this is call 1/1 again


# --- Integration: wired through the real Strands HookRegistry ---
#
# The tests above call hook.check()/reset() directly with duck-typed stand-ins,
# which never exercises register_hooks() itself - i.e. they can't catch a typo'd
# event class or a callback registered to the wrong event. These use the real
# strands.hooks classes and dispatch, so they'd catch a broken registration.

from strands.hooks import BeforeInvocationEvent, BeforeToolCallEvent, HookRegistry


def make_registry(hook: RateLimiterHook) -> HookRegistry:
    registry = HookRegistry()
    registry.add_hook(hook)
    return registry


def real_tool_use_event(name: str) -> BeforeToolCallEvent:
    return BeforeToolCallEvent(
        agent=None,
        selected_tool=None,
        tool_use={"name": name, "toolUseId": "t1", "input": {}},
        invocation_state={},
    )


def test_registers_check_on_before_tool_call_event():
    hook = RateLimiterHook(max_calls=1)
    registry = make_registry(hook)

    registry.invoke_callbacks(real_tool_use_event("utilify_get_promotions"))
    event, _ = registry.invoke_callbacks(real_tool_use_event("utilify_get_promotions"))

    assert event.cancel_tool is not None


def test_registers_reset_on_before_invocation_event():
    hook = RateLimiterHook(max_calls=1)
    registry = make_registry(hook)

    registry.invoke_callbacks(real_tool_use_event("utilify_get_promotions"))
    registry.invoke_callbacks(BeforeInvocationEvent(agent=None))

    event, _ = registry.invoke_callbacks(real_tool_use_event("utilify_get_promotions"))
    assert not event.cancel_tool  # new invocation reset the count (default is False, not None)


# --- Lambda-backed mode ---
#
# RateLimiterHook(lambda_function_name=...) delegates counting to a Lambda
# function instead of a local dict (see hooks.py's class docstring for why).
# A fake lambda_client stands in for boto3's real "lambda" client - the hook
# only calls .invoke(FunctionName=, InvocationType=, Payload=) and reads
# response["Payload"].read() / response.get("FunctionError"), so a fake
# implementing just that contract behaves identically for testing purposes,
# with no real AWS call, credentials, or network involved.

import json

from hooks import RATE_LIMITER_LAMBDA_NAME


class FakePayload:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeLambdaClient:
    """Backed by a dict shared across instances - standing in for the
    DynamoDB table that's actually shared across containers in production."""

    def __init__(self, shared_counts: dict[str, int] | None = None):
        self.counts = shared_counts if shared_counts is not None else {}
        self.invoke_calls = 0

    def invoke(self, FunctionName, InvocationType, Payload):
        self.invoke_calls += 1
        body = json.loads(Payload)
        counter_id = f"{body['invocation_id']}#{body['tool_name']}"
        self.counts[counter_id] = self.counts.get(counter_id, 0) + 1
        count = self.counts[counter_id]
        result = {"count": count, "blocked": count > body["max_calls"]}
        return {"Payload": FakePayload(json.dumps(result).encode())}


class FailingLambdaClient:
    def __init__(self):
        self.invoke_calls = 0

    def invoke(self, **kwargs):
        self.invoke_calls += 1
        raise RuntimeError("boom - simulated Lambda outage")


def lambda_hook(max_calls: int, lambda_client) -> RateLimiterHook:
    hook = RateLimiterHook(
        max_calls=max_calls,
        lambda_function_name=RATE_LIMITER_LAMBDA_NAME,
        lambda_client=lambda_client,
    )
    hook.reset(event=None)  # assigns invocation_id, as BeforeInvocationEvent would
    return hook


def test_lambda_mode_blocks_using_the_lambda_provided_count():
    hook = lambda_hook(max_calls=1, lambda_client=FakeLambdaClient())
    hook.check(tool_call_event("utilify_get_promotions"))

    event = tool_call_event("utilify_get_promotions")
    hook.check(event)
    assert event.cancel_tool is not None


def test_lambda_mode_shares_count_across_separate_hook_instances():
    # The scenario this mode exists for: two hook instances (e.g. two
    # different warm containers) handling calls for the *same* turn should
    # still see one shared count, not two independent ones.
    shared_backend = {}
    hook_a = lambda_hook(max_calls=2, lambda_client=FakeLambdaClient(shared_backend))
    hook_b = lambda_hook(max_calls=2, lambda_client=FakeLambdaClient(shared_backend))
    hook_b.invocation_id = hook_a.invocation_id  # same turn, different container

    hook_a.check(tool_call_event("utilify_get_promotions"))
    hook_a.check(tool_call_event("utilify_get_promotions"))

    # hook_b's own local dict has never seen this tool, but the shared
    # backend has - it should still block on what would be the 3rd call.
    event = tool_call_event("utilify_get_promotions")
    hook_b.check(event)
    assert event.cancel_tool is not None


def test_lambda_mode_falls_back_to_local_counting_on_failure():
    hook = lambda_hook(max_calls=5, lambda_client=FailingLambdaClient())

    event = tool_call_event("utilify_get_promotions")
    hook.check(event)  # must not raise - fails open per the class docstring

    assert event.cancel_tool is None
    assert hook.counts["utilify_get_promotions"] == 1  # fell back to local counting


def test_lambda_mode_stops_retrying_lambda_within_the_same_turn_after_a_failure():
    client = FailingLambdaClient()
    hook = lambda_hook(max_calls=5, lambda_client=client)

    for _ in range(3):
        hook.check(tool_call_event("utilify_get_promotions"))

    assert client.invoke_calls == 1  # only tried once, then fell back locally


def test_lambda_mode_retries_lambda_again_on_the_next_turn():
    client = FailingLambdaClient()
    hook = lambda_hook(max_calls=5, lambda_client=client)
    hook.check(tool_call_event("utilify_get_promotions"))
    assert client.invoke_calls == 1

    hook.reset(event=None)  # next turn
    hook.check(tool_call_event("utilify_get_promotions"))
    assert client.invoke_calls == 2  # gave the Lambda a fresh chance


def test_default_mode_never_touches_an_injected_lambda_client():
    # lambda_function_name=None (the default) means local-only, even if a
    # client happens to be passed in.
    client = FakeLambdaClient()
    hook = RateLimiterHook(max_calls=5, lambda_client=client)

    hook.check(tool_call_event("utilify_get_promotions"))
    assert client.invoke_calls == 0
