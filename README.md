# Utility Providers Agent

An AI agent, built with the [Strands Agents](https://strandsagents.com/) SDK,
that helps a customer shop for household utility providers and plan a monthly
budget. Follows the module progression from the
[Strands Agents Hands-On Workshop](https://github.com/aws-samples/sample-strands-agents-hands-on-workshop):
agent loop + tools, hooks, skills + steering, and session persistence.

## The harness

Beyond the bare agent loop and tools, this agent has a full harness around it:

| Layer                        | What it does                                                                                                                                                                                                      | Where                  |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| **Hooks**                    | `RateLimiterHook` caps each tool at 4 calls per turn, so a confused model can't loop forever                                                                                                                      | `hooks.py`             |
| **Skills**                   | `provider-shopping` and `budget-estimate` give the model a step-by-step workflow to follow                                                                                                                        | `skills/`              |
| **Steering (deterministic)** | `BudgetWorkflowHandler` blocks `estimate_monthly_budget` if a provider name wasn't actually returned by an earlier `find_providers`/`get_promotions` call — stops the agent from inventing a provider             | `steering_handlers.py` |
| **Steering (LLM guardrail)** | `ToneGuardrailHandler` reviews every response for invented details, overpromised savings, or a missing "estimates vary" disclosure                                                                                | `steering_handlers.py` |
| **Session manager**          | `FileSessionManager` persists the conversation to `./sessions/`, so the agent remembers a customer across restarts when you reuse `--session-id` (local chat only — see `main.py` note in [DEPLOY.md](DEPLOY.md)) | `chat.py`              |

## What it does

Ask the agent things like:

- "What providers are available in zip code 78701?"
- "What providers serve Chicago, IL for electricity and internet?"
- "Are there any promotions on Google Fiber?"
- "What's the cheapest internet promotion right now?"
- "I want Austin Energy for electricity and Google Fiber for internet — what's my monthly budget?"

## Tools

| Tool                      | Purpose                                                                                               |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `find_providers`          | Look up water, gas, electricity, and internet providers serving a zip code, or a city + state         |
| `get_promotions`          | Look up current promotions by provider name or service type                                           |
| `estimate_monthly_budget` | Combine the customer's chosen providers into a monthly total, applying any active promotion discounts |

Provider coverage and rates are mock data (`utility_provider_tools.py`) covering
five sample metro areas: Seattle WA, Austin TX, Chicago IL, Atlanta GA, and
San Francisco CA. Swap in a real provider API to make it production-ready.

## How do I run it?

```bash
pip install -r requirements.txt
python chat.py                       # uses the default session id
python chat.py --session-id alice    # resume/keep a named session
```

You need Python 3.10+ and AWS credentials with Amazon Bedrock access (Strands
uses Bedrock by default). See `chat.py` for how to switch to an Amazon Nova
model (e.g. for AWS hackathon credits) or run fully locally with Ollama.

Type `quit`, `exit`, or press Ctrl+C to stop the chat — your conversation is
saved to `./sessions/` either way, so running with the same `--session-id`
again picks up where you left off.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

31 unit tests cover the tools, the rate limiter, and the budget-workflow
guardrail directly — no AWS credentials needed. `tests/test_live_agent.py`
calls a real model and is opt-in only (`RUN_LIVE_TESTS=1 pytest tests/test_live_agent.py`);
see [DEPLOY.md](DEPLOY.md).

## Deploying it

`main.py` wraps the same agent for **Amazon Bedrock AgentCore Runtime** (a
managed, serverless host for agents). See [DEPLOY.md](DEPLOY.md) for what it
provisions, costs, and how to run `./deploy.sh`.

## Files

| File                                | Purpose                                                                                              |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `chat.py`                           | Interactive multi-turn CLI chat loop, wired up with hooks, skills, steering, and session persistence |
| `main.py`                           | Deployable entrypoint for AgentCore Runtime (same agent, minus local session persistence)            |
| `utility_provider_tools.py`         | Mock provider/promotion data and the three `@tool`-decorated functions                               |
| `hooks.py`                          | `RateLimiterHook` — caps tool calls per turn                                                         |
| `steering_handlers.py`              | `BudgetWorkflowHandler` (deterministic) and `ToneGuardrailHandler` (LLM-based) guardrails            |
| `skills/provider-shopping/SKILL.md` | Workflow for helping a customer discover providers and promotions                                    |
| `skills/budget-estimate/SKILL.md`   | Workflow for calculating the combined monthly budget                                                 |
| `tests/`                            | Pytest unit tests (offline) plus an opt-in live-agent smoke test                                     |
| `deploy.sh` / `DEPLOY.md`           | Script and docs for deploying to AgentCore Runtime                                                   |
| `requirements.txt`                  | Deps for local `chat.py` (`strands-agents`)                                                          |
| `requirements-deploy.txt`           | Adds `bedrock-agentcore`, `aws-opentelemetry-distro`, `boto3` for `main.py`                          |
| `requirements-dev.txt`              | Adds `pytest` for running the test suite                                                             |
| `sessions/`                         | Persisted conversation history per `--session-id` (created on first run, gitignored)                 |
| `agentcore-project/`                | Generated by `deploy.sh` — the scaffolded AgentCore CDK project (gitignored)                         |
