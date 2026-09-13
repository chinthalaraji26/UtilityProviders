# Movers Helper Agent

An AI agent, built with the [Strands Agents](https://strandsagents.com/) SDK,
that helps a customer search real Texas utility plans, compare them, and
enroll with a chosen provider. Follows the module progression from the
[Strands Agents Hands-On Workshop](https://github.com/aws-samples/sample-strands-agents-hands-on-workshop):
agent loop + tools, hooks, skills + steering.

## The harness

Beyond the bare agent loop and tools, this agent has a full harness around it:

| Layer                         | What it does                                                                                                                                                                                     | Where                  |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| **Hooks**                      | `RateLimiterHook` caps each tool at 4 calls per turn, so a confused model can't loop forever                                                                                                  | `hooks.py`             |
| **Skills**                     | `utility-enrollment` gives the model a step-by-step workflow: search, compare, confirm, enroll                                                                                                | `skills/`              |
| **Steering (human-in-loop)**   | `EnrollmentConfirmationHandler` blocks enrollment/solar-inquiry tool calls until the customer's own message explicitly confirms — a human always signs off before those real-world actions run | `steering_handlers.py` |
| **Steering (LLM guardrail)**   | `ToneGuardrailHandler` reviews every response for invented details, overpromised savings, or falsely claiming enrollment is complete                                                          | `steering_handlers.py` |

## What it does

Ask the agent things like:

- "What electricity plans are available in zip code 78701?"
- "Compare the top internet plans for my address."
- "Are there any current promotions on electricity in Austin?"
- "I'm moving next month — what do I need to set up?"
- "Sign me up for the plan we just looked at" (only proceeds once you confirm)

## Tools

| Tool                  | Purpose                                                                                                    |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| `utilify_*` (8 tools)  | Real, live Texas utility plan search, comparison, promotions, move checklists, and enrollment via the [Utilify MCP server](https://utilify.io/mcp-docs) (`mcp_providers.py`), no API key required |

This is the agent's only tool source, so it's Texas-only - there's no mock
fallback data for other states.

## How do I run it?

```bash
pip install -r requirements-deploy.txt
python main.py
```

This starts a local server on `http://127.0.0.1:8080` - the same contract
AgentCore Runtime uses in production:

```bash
curl -X POST http://127.0.0.1:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{"prompt": "What electricity plans are available in zip code 78701?"}'
```

You need Python 3.10+ and AWS credentials with Amazon Bedrock access (Strands
uses Bedrock by default). See `main.py` for how to switch to an Amazon Nova
model (e.g. for AWS hackathon credits) or run fully locally with Ollama.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Unit tests cover the rate limiter and the entrypoint's payload parsing
directly — no AWS credentials needed. `tests/test_live_agent.py` calls a
real model and is opt-in only (`RUN_LIVE_TESTS=1 pytest tests/test_live_agent.py`);
see [DEPLOY.md](DEPLOY.md).

## Deploying it

`main.py` also *is* the deployable entrypoint for **Amazon Bedrock AgentCore
Runtime** (a managed, serverless host for agents) - no separate build step.
See [DEPLOY.md](DEPLOY.md) for what it provisions, costs, and how to run
`./deploy.sh`.

## Files

| File                                  | Purpose                                                                                    |
| -------------------------------------- | ------------------------------------------------------------------------------------------ |
| `main.py`                              | The agent: entrypoint for both local runs and AgentCore Runtime deployment                 |
| `mcp_providers.py`                     | Wires in the live Utilify MCP server (`utilify_*` tools) — the agent's only tool source     |
| `hooks.py`                             | `RateLimiterHook` — caps tool calls per turn                                               |
| `steering_handlers.py`                 | `EnrollmentConfirmationHandler` (deterministic human-in-the-loop) and `ToneGuardrailHandler` (LLM-based) guardrails |
| `skills/utility-enrollment/SKILL.md`   | Workflow for searching, comparing, and enrolling with a real Texas provider via Utilify     |
| `tests/`                               | Pytest unit tests (offline) plus an opt-in live-agent smoke test                            |
| `deploy.sh` / `DEPLOY.md`              | Script and docs for deploying to AgentCore Runtime                                          |
| `requirements-deploy.txt`              | Deps to run `main.py`, locally or deployed (`strands-agents`, `bedrock-agentcore`, `aws-opentelemetry-distro`, `boto3`) |
| `requirements-dev.txt`                 | Adds `pytest` for running the test suite                                                    |
| `agentcore-project/`                   | Generated by `deploy.sh` — the scaffolded AgentCore CDK project (gitignored)                |
