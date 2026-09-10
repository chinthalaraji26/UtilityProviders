"""Steering guardrails for the Utility Bot.

Two handlers, following the Module 3 (Skills + Steering) pattern from the
Strands Agents Hands-On Workshop:

- EnrollmentConfirmationHandler: deterministic. Keeps a human in the loop
  before the agent kicks off a real-world enrollment/solar-inquiry action via
  the Utilify MCP tools (mcp_providers.py) - the customer's own message must
  explicitly confirm they want to proceed first.
- ToneGuardrailHandler: LLM-based. Reviews each response for overpromising,
  invented details, and missing the "estimates vary" disclosure.
"""

from strands.vended_plugins.steering import (
    SteeringHandler, LLMSteeringHandler,
    Proceed, Guide, ToolSteeringAction,
)


class EnrollmentConfirmationHandler(SteeringHandler):
    """Deterministic handler: a human must explicitly confirm before enrollment starts.

    Rule: utilify_initiate_signup and utilify_request_solar have real-world
    consequences for the customer (kicking off a signup flow, or sharing
    their contact info with third-party installers), so the agent can't
    decide on its own to call them. They may only run when the customer's
    own most recent message explicitly says to proceed.

    This is the "final action" of the enrollment workflow, and even once it
    runs, utilify_initiate_signup only returns a link - the customer still
    has to open it and finish enrolling on the provider's own site, so a
    human stays in the loop for the actual signup too.
    """

    name = "enrollment-confirmation"

    GATED_TOOLS = {"utilify_initiate_signup", "utilify_request_solar"}
    CONFIRMATION_PHRASES = [
        "yes", "yep", "yeah", "confirm", "confirmed", "go ahead", "sounds good",
        "let's do it", "lets do it", "sign me up", "sign us up", "enroll me",
        "enroll us", "proceed", "do it", "please do", "ok", "okay",
    ]

    async def steer_before_tool(self, *, agent, tool_use, **kwargs) -> ToolSteeringAction:
        tool_name = tool_use.get("name")
        if tool_name not in self.GATED_TOOLS:
            return Proceed(reason="Not an enrollment action")

        print(f"[STEERING] 🔍 {tool_name} attempted — checking for explicit customer confirmation...")

        last_user_text = _last_user_message_text(agent).lower()
        if not any(phrase in last_user_text for phrase in self.CONFIRMATION_PHRASES):
            print("[STEERING] ⚠️  Blocked: no explicit confirmation in the customer's last message")
            return Guide(
                reason=f"'{tool_name}' has a real-world effect for the customer, so it needs their "
                "explicit, current go-ahead - not an earlier expression of interest. Summarize what "
                "you're about to do (which plan/provider, and for signup, that they'll get a link "
                "they must open themselves to finish with the provider) and ask the customer to "
                "confirm before calling this tool again."
            )

        print("[STEERING] ✅ Explicit confirmation found — proceeding, human stays in the loop via the signup link")
        return Proceed(reason="Customer explicitly confirmed in their last message")


def _last_user_message_text(agent) -> str:
    """Return the text of the most recent user message in the conversation."""
    for message in reversed(agent.messages):
        if message.get("role") == "user":
            return " ".join(
                block.get("text", "") for block in message.get("content", []) if isinstance(block, dict)
            )
    return ""


class ToneGuardrailHandler(LLMSteeringHandler):
    name = "tone-guardrail"

    def __init__(self):
        super().__init__(
            system_prompt="""You are evaluating Utility Bot's responses.
Ensure the agent follows these communication guidelines:

- Never state a provider, rate, or promotion that wasn't returned by a tool call - no inventing details.
- Never state a monthly cost estimate as a guaranteed bill - it must be clear this is a typical-usage estimate.
- Don't overpromise specific savings or guarantee a promotion will still be active when the customer signs up.
- Don't pressure the customer toward a specific provider - present options, recommend, but let them choose.
- Never state that enrollment/signup is complete after calling utilify_initiate_signup - it only returns
  a link. Make clear the customer must open it and finish enrolling on the provider's own site.
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
