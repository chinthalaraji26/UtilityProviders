"""Unit tests for steering_handlers.py.

ToneGuardrailHandler.steer_before_tool is a no-op override; it never calls
the model, so this can be tested directly with no network/LLM dependency.
No async pytest plugin is installed in this project, so run the coroutine
with asyncio.run() from a plain sync test rather than adding one.
"""

import asyncio

from steering_handlers import ToneGuardrailHandler


def test_tone_guardrail_never_gates_tool_calls():
    # Regression test: LLMSteeringHandler (ToneGuardrailHandler's base
    # class) provides a default steer_before_tool that would otherwise run
    # every tool call through this class's tone-focused system_prompt too -
    # not what that prompt is written to judge, and it can raise Interrupt,
    # which main.py has no human-in-the-loop handling for (an interrupt's
    # raw internal representation would leak straight into the
    # customer-facing response). Tool-call gating is EnrollmentConfirmationHandler's
    # job; this asserts ToneGuardrailHandler stays out of it regardless of
    # which tool or input it's asked about.
    handler = ToneGuardrailHandler()

    result = asyncio.run(handler.steer_before_tool(
        agent=None, tool_use={"name": "utilify_initiate_signup", "input": {"anything": "at all"}}
    ))

    assert type(result).__name__ == "Proceed"
