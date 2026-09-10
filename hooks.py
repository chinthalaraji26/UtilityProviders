"""Shared hooks for the Utility Bot.

Used by the main.py entrypoint.
"""

from strands.hooks import (
    HookProvider, HookRegistry,
    BeforeInvocationEvent, BeforeToolCallEvent,
)


class RateLimiterHook(HookProvider):
    """Caps each tool at max_calls per agent invocation (one user turn)."""

    def __init__(self, max_calls: int = 4):
        self.max_calls = max_calls
        self.counts: dict[str, int] = {}

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.reset)
        registry.add_callback(BeforeToolCallEvent, self.check)

    def reset(self, event: BeforeInvocationEvent) -> None:
        """Reset counts at the start of each invocation."""
        self.counts = {}

    def check(self, event: BeforeToolCallEvent) -> None:
        """Check and enforce the rate limit before each tool call."""
        name = event.tool_use["name"]
        self.counts[name] = self.counts.get(name, 0) + 1

        if self.counts[name] > self.max_calls:
            event.cancel_tool = (
                f"'{name}' hit the {self.max_calls}-call limit for this turn. "
                "Do NOT call this tool again - answer with what you already have."
            )
            print(f"[HOOK] BLOCKED: {name} exceeded {self.max_calls} calls this turn!")
