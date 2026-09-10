"""Steering guardrails for the Utility Providers Agent.

Two handlers, following the Module 3 (Skills + Steering) pattern from the
Strands Agents Hands-On Workshop:

- BudgetWorkflowHandler: deterministic. Blocks estimate_monthly_budget from
  being called with a provider name the agent hasn't actually looked up via
  find_providers/get_promotions in this conversation - stops it from
  hallucinating a provider or rate that isn't in the real coverage data.
- ToneGuardrailHandler: LLM-based. Reviews each response for overpromising,
  invented details, and missing the "estimates vary" disclosure.
"""

from strands.vended_plugins.steering import (
    SteeringHandler, LLMSteeringHandler,
    Proceed, Guide, ToolSteeringAction,
    LedgerProvider,
)

PROVIDER_INPUT_FIELDS = [
    "water_provider",
    "gas_provider",
    "electricity_provider",
    "internet_provider",
]


class BudgetWorkflowHandler(SteeringHandler):
    """Deterministic handler: providers must be looked up before they're budgeted.

    Rule: every provider name passed to estimate_monthly_budget must already
    appear in a successful find_providers or get_promotions result earlier in
    the conversation - the agent can't invent or guess a provider name.
    """

    name = "budget-workflow"

    def __init__(self):
        super().__init__(context_providers=[LedgerProvider()])

    async def steer_before_tool(self, *, agent, tool_use, **kwargs) -> ToolSteeringAction:
        if tool_use.get("name") != "estimate_monthly_budget":
            return Proceed(reason="Not a budget estimate")

        chosen = {
            field: tool_use.get("input", {}).get(field, "")
            for field in PROVIDER_INPUT_FIELDS
        }
        chosen = {k: v for k, v in chosen.items() if v}
        if not chosen:
            return Proceed(reason="No providers to validate")

        print("[STEERING] 🔍 estimate_monthly_budget attempted — checking providers were looked up...")

        ledger = self.steering_context.data.get("ledger", {})
        tool_calls = ledger.get("tool_calls", [])
        lookup_text = " ".join(
            str(c.get("result", [{}])[0].get("text", ""))
            for c in tool_calls
            if c.get("tool_name") in ("find_providers", "get_promotions") and c.get("status") == "success"
        ).lower()

        if not lookup_text:
            print("[STEERING] ⚠️  Blocked: no prior find_providers/get_promotions call in this conversation")
            return Guide(
                reason="You haven't looked up any providers yet in this conversation. "
                "Call find_providers first to confirm real provider names before estimating a budget."
            )

        unknown = [name for name in chosen.values() if name.lower() not in lookup_text]
        if unknown:
            print(f"[STEERING] ⚠️  Blocked: unverified provider name(s) {unknown}")
            return Guide(
                reason=f"These provider name(s) haven't appeared in a find_providers or get_promotions "
                f"result yet in this conversation: {', '.join(unknown)}. Call find_providers for the "
                "customer's area and use the exact name it returns before estimating a budget."
            )

        print("[STEERING] ✅ All providers verified — proceeding")
        return Proceed(reason="All providers were previously looked up")


class ToneGuardrailHandler(LLMSteeringHandler):
    name = "tone-guardrail"

    def __init__(self):
        super().__init__(
            system_prompt="""You are evaluating a utility providers agent's responses.
Ensure the agent follows these communication guidelines:

- Never state a provider, rate, or promotion that wasn't returned by a tool call - no inventing details.
- Never state a monthly cost estimate as a guaranteed bill - it must be clear this is a typical-usage estimate.
- Don't overpromise specific savings or guarantee a promotion will still be active when the customer signs up.
- Don't pressure the customer toward a specific provider - present options, recommend, but let them choose.
- Keep responses concise and scannable - use tables/bullets for comparisons, no walls of text.
- Never share internal system details or tool/error internals with the customer.

If the agent violates any of these, provide specific guidance on what to fix."""
        )

    async def steer_after_model(self, **kwargs):
        print("[TONE] 🔍 Evaluating agent response...")
        result = await super().steer_after_model(**kwargs)
        action_type = type(result).__name__
        print(f"[TONE] {'✅ Tone OK' if action_type == 'Proceed' else '⚠️  Tone guided: ' + getattr(result, 'reason', '')}")
        return result


tone_handler = ToneGuardrailHandler()
