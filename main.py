"""Deployable entrypoint for Amazon Bedrock AgentCore Runtime.

Wraps the same agent as chat.py - tools, rate-limiter hook, skills, and
steering guardrails - in a BedrockAgentCoreApp so the `agentcore` CLI can
package and deploy it. No FileSessionManager here: AgentCore Runtime keeps a
session's requests pinned to the same warm container, so the in-memory
`agent.messages` on the module-level singleton below already carries context
across turns for a session, the same way Module 5 of the workshop does it.

See DEPLOY.md for how to package and deploy this with the `agentcore` CLI.
"""

import json
import logging

from strands import Agent, AgentSkills
from strands.agent.conversation_manager import SlidingWindowConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from utility_provider_tools import find_providers, get_promotions, estimate_monthly_budget
from steering_handlers import BudgetWorkflowHandler, tone_handler
from hooks import RateLimiterHook

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

SYSTEM_PROMPT = """You are a helpful utility providers agent. You help customers:
1. Find water, gas, electricity, and internet providers available in their area
   (by zip code, or by city + state).
2. Check current promotions those providers are running.
3. Once the customer has picked a provider for one or more services, estimate
   their combined monthly utility budget, including any active promotion discounts.

When a customer needs help, activate the appropriate skill for step-by-step guidance.

Important guidelines:
- Use find_providers to discover what's available before recommending anything -
  don't guess at provider names.
- Proactively mention relevant active promotions when presenting provider options.
- Only call estimate_monthly_budget once the customer has told you which provider
  they want for each service they care about - don't assume choices for them.
- Be clear that estimates are for a typical household and actual bills vary with usage.
- Be warm, concise, and use tables or bullet points for readability when comparing options.
- If there are previous messages in the conversation history, use that context to
  continue helping the customer without asking them to repeat information."""

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = Agent(
            tools=[find_providers, get_promotions, estimate_monthly_budget],
            hooks=[RateLimiterHook(max_calls=4)],
            plugins=[
                AgentSkills(skills=["./skills"]),
                BudgetWorkflowHandler(),
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
