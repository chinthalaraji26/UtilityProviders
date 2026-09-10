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
        event = tool_call_event("find_providers")
        hook.check(event)
        assert event.cancel_tool is None


def test_blocks_calls_beyond_the_limit():
    hook = RateLimiterHook(max_calls=2)
    for _ in range(2):
        hook.check(tool_call_event("get_promotions"))

    event = tool_call_event("get_promotions")
    hook.check(event)
    assert event.cancel_tool is not None
    assert "2-call limit" in event.cancel_tool


def test_counts_are_tracked_per_tool_independently():
    hook = RateLimiterHook(max_calls=1)
    hook.check(tool_call_event("find_providers"))

    other_event = tool_call_event("get_promotions")
    hook.check(other_event)
    assert other_event.cancel_tool is None  # different tool, own count


def test_reset_clears_counts_between_turns():
    hook = RateLimiterHook(max_calls=1)
    hook.check(tool_call_event("find_providers"))

    hook.reset(event=None)

    event = tool_call_event("find_providers")
    hook.check(event)
    assert event.cancel_tool is None  # count was reset, so this is call 1/1 again
