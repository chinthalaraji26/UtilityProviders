"""Movers Helper Agent: entrypoint for Amazon Bedrock AgentCore Runtime.

Wraps the agent - tools, rate-limiter hook, skills, and steering guardrails -
in a BedrockAgentCoreApp so the `agentcore` CLI can package and deploy it. No
FileSessionManager here: AgentCore Runtime keeps a session's requests pinned
to the same warm container, so the in-memory `agent.messages` on the
module-level singleton below already carries context across turns for a
session, the same way Module 5 of the workshop does it.

Run it locally with `python main.py` - it starts a local server on
http://127.0.0.1:8080, the same contract AgentCore Runtime uses:

    curl -X POST http://127.0.0.1:8080/invocations \\
        -H "Content-Type: application/json" \\
        -d '{"prompt": "What electricity plans are available in 78701?"}'

See DEPLOY.md for how to package and deploy this with the `agentcore` CLI.
"""

import json
import logging
import sys

from strands import Agent, AgentSkills
from strands.agent.conversation_manager import SlidingWindowConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from mcp_providers import utilify_tools
from steering_handlers import EnrollmentConfirmationHandler, tone_handler
from hooks import RATE_LIMITER_LAMBDA_NAME, RateLimiterHook

# The model may stream emoji/special characters that some consoles' default
# encoding (e.g. Windows cp1252) can't print, which otherwise crashes the
# process mid-response when running locally. Force UTF-8 stdout so any
# character just prints correctly, on any platform.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

SYSTEM_PROMPT = """You are Movers Helper Agent, a helpful assistant. You help customers in Texas:
1. Search and compare real electricity, internet, gas, water, sewer, trash, and
   home-security plans available at their address, using the Utilify tools (utilify_*).
2. Check current promotions and deals on those plans.
3. Plan a move with a personalized utility setup checklist.
4. When they're ready, enroll with a chosen plan - or connect with a licensed
   solar installer - as the final action, only once they explicitly confirm.

When a customer needs help, activate the appropriate skill for step-by-step guidance.

Important guidelines:
- Utilify only covers Texas addresses. If the customer isn't in Texas, say so
  plainly rather than guessing at coverage or prices.
- Use utilify_search_utility_providers to discover what's available before
  recommending anything - don't guess at plans, providers, or prices.
- Proactively mention relevant active promotions when presenting plan options.
- Enrollment (utilify_initiate_signup) and the solar-inquiry handoff
  (utilify_request_solar) are real-world actions - always summarize what
  you're about to do and get the customer's explicit go-ahead first.
  utilify_initiate_signup only returns a link; never say the customer is
  enrolled until they've finished it themselves with the provider.
- Be warm, concise, and use tables or bullet points for readability when comparing options.
- If there are previous messages in the conversation history, use that context to
  continue helping the customer without asking them to repeat information."""

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = Agent(
            tools=[utilify_tools],
            hooks=[RateLimiterHook(max_calls=4, lambda_function_name=RATE_LIMITER_LAMBDA_NAME)],
            plugins=[
                AgentSkills(skills=["./skills"]),
                EnrollmentConfirmationHandler(),
                tone_handler,
            ],
            system_prompt=SYSTEM_PROMPT,
            conversation_manager=SlidingWindowConversationManager(window_size=20),
        )
    return _agent


@app.entrypoint
def invoke(payload, context):
    raw_prompt = payload.get("prompt")
    try:
        parsed = json.loads(raw_prompt)
        prompt = parsed.get("prompt", raw_prompt)
    except (TypeError, json.JSONDecodeError):
        prompt = raw_prompt

    if not prompt:
        raise ValueError("Missing required field: prompt")

    agent = get_agent()
    response = agent(prompt)
    return str(response).strip()


if __name__ == "__main__":
    app.run()
