"""Interactive multi-turn chat for the Utility Providers Agent, with a full harness:

- Hooks: a rate limiter caps each tool at a few calls per turn (guards against loops).
- Skills + steering: workflow skills guide the shopping/budget flow, a deterministic
  guardrail blocks budgeting with an unverified provider name, and an LLM tone
  guardrail checks each response before it's shown.
- Session manager: conversation history is persisted to disk, so the agent
  remembers the customer across restarts when you reuse the same --session-id.

Built with the Strands Agents SDK, following the module progression from the
Strands Agents Hands-On Workshop:
https://github.com/aws-samples/sample-strands-agents-hands-on-workshop

    pip install -r requirements.txt
    python chat.py                       # uses the default session id
    python chat.py --session-id alice    # resume/keep a named session

Type 'quit', 'exit', or press Ctrl+C to stop.
"""

import argparse
import sys

from strands import Agent, AgentSkills
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager
from utility_provider_tools import find_providers, get_promotions, estimate_monthly_budget
from steering_handlers import BudgetWorkflowHandler, tone_handler
from hooks import RateLimiterHook

# The model may stream emoji/special characters that Windows' default console
# encoding (cp1252) can't print, which otherwise crashes the whole process
# mid-response. Force UTF-8 stdout so any character just prints correctly.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# AWS-sponsored events / AWS credits: credits only cover Amazon Nova models, not Claude.
# To switch, pass model=BedrockModel(model_id="...") to Agent(...).
# Nova model IDs: https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards-amazon.html
#   amazon.nova-micro-v1:0  — fastest, text-only, lowest cost
#   amazon.nova-lite-v1:0   — low-cost, multimodal (text, image, video)
#   amazon.nova-pro-v1:0   — balanced accuracy/speed, multimodal (recommended)
#
# Run locally without AWS credentials using Ollama (https://ollama.com/download):
#   1. Install Ollama and run: ollama pull llama3.1
#   2. pip install strands-agents[ollama]
#   3. Use OllamaModel: from strands.models import OllamaModel
#      model = OllamaModel(host="http://localhost:11434", model_id="llama3.1")
#      agent = Agent(model=model, tools=[...], hooks=[...], plugins=[...],
#                     session_manager=..., system_prompt=...)
#   Other models with tool support: llama3.2, qwen2.5, qwen3, mistral


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


def main():
    parser = argparse.ArgumentParser(description="Multi-turn chat with a persistent utility providers agent.")
    parser.add_argument(
        "--session-id",
        default="utility-session-001",
        help="Session id to persist/resume (default: utility-session-001).",
    )
    args = parser.parse_args()

    # FileSessionManager persists conversation state to ./sessions. Reusing the
    # same session_id across runs restores the prior conversation, so memory
    # survives both turns and full restarts.
    session_manager = FileSessionManager(
        session_id=args.session_id,
        storage_dir="./sessions",
    )

    agent = Agent(
        tools=[find_providers, get_promotions, estimate_monthly_budget],
        hooks=[RateLimiterHook(max_calls=4)],
        plugins=[
            AgentSkills(skills=["./skills"]),
            BudgetWorkflowHandler(),
            tone_handler,
        ],
        system_prompt=SYSTEM_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=20),
        session_manager=session_manager,
    )

    restored = len(agent.messages)
    print(f"Utility Providers Agent (session: {args.session_id}) - type 'quit' to exit.")
    if restored:
        print(f"Restored {restored} message(s) from a previous session.")
    print('Try: "What providers are available in zip code 78701?"')
    print("Then quit and run again with the same --session-id - it remembers you.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! Your conversation is saved.")
            break

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye! Your conversation is saved.")
            break
        if not user_input:
            continue

        # The agent prints its own streamed response via the default callback handler.
        print("\nAgent: ", end="")
        agent(user_input)
        print()


if __name__ == "__main__":
    main()
