# Utility Bot

*Search real Texas utility plans, compare them, and enroll with a real provider — one conversation, with a human always signing off before anything real happens.*

## Inspiration

Shopping for utilities means five browser tabs: find who even serves your
address, dig through pricing pages for promotions that are still active, do
the math to combine services into a monthly number, then enroll separately
with whoever you picked. That's a lot of manual cross-referencing for
something that should be one conversation.

Fresh off the Strands Agents Hands-On Workshop, we saw the real question: not
whether an agent *could* do this, but whether it could be trusted to — never
inventing a provider, never enrolling someone without asking. Utility Bot is
our answer: an agent that goes from "what's near me?" to "you're enrolled"
without crossing that trust line.

## What it does

For a Texas address, Utility Bot:

1. **Searches real, live plans** — electricity, internet, gas, water, sewer,
   trash, even solar — via [Utilify's MCP server](https://utilify.io/mcp-docs).
2. **Compares options and surfaces active promotions.**
3. **Builds a move-in checklist.**
4. **Enrolls** — once the customer has picked a plan.

That last step got the most care: enrollment has real consequences, so the
agent must summarize exactly what it's about to do and get explicit
go-ahead first — and even then it only hands back a signup link, because
finishing on the provider's own site stays a human's job.

## How we built it

Built on the [Strands Agents SDK](https://strandsagents.com/), following the
[Hands-On Workshop](https://github.com/aws-samples/sample-strands-agents-hands-on-workshop)'s
progression — agent loop, hooks, skills, steering — plus a live MCP
integration gated by our own human-in-the-loop guardrail.

- **Tools**: one `MCPClient` wired to Utilify's public MCP server (no API
  key) brings in eight tools for real Texas data. We started with a parallel
  mock multi-city toolset too, but consolidated onto Utilify alone so every
  answer is real, not a demo of the pattern.
- **Hooks**: `RateLimiterHook` caps every tool at 4 calls/turn so a confused
  model can't loop forever.
- **Skills**: one `SKILL.md` workflow (`utility-enrollment`) — search,
  compare, confirm, enroll.
- **Steering**: `EnrollmentConfirmationHandler` deterministically blocks
  signup/solar tools unless the customer's *most recent* message explicitly
  confirms — no acting on an earlier "I'm interested." `ToneGuardrailHandler`
  is an LLM check catching overpromising and false "enrollment done" claims.
- **Deployment**: `main.py` is one entrypoint, run two ways — a local HTTP
  server (`python main.py`) or, via `deploy.sh`, packaged onto **Amazon
  Bedrock AgentCore Runtime** through a CDK-managed CloudFormation stack.
- **Testing**: offline pytest for the rate limiter and request parsing; an
  opt-in live suite that hits a real model and checks the human-in-the-loop
  guardrail actually holds.

## Challenges we ran into

- **Blocking the right thing, not everything.** We needed the enrollment
  gate to trigger on the customer's *current* message, not just anywhere
  earlier in the conversation — otherwise an old "I'm interested" reads as
  standing consent.
- **Mock data was a liability, not a shortcut.** Running mock and live tools
  side by side meant two answers to the same question. We cut the mock layer
  entirely — one source of truth, even at the cost of Texas-only coverage.
- **Trust, but verify the MCP contract.** Utilify's docs describe its tools,
  but only connecting live and listing them confirmed our guardrail's
  tool-name allowlist would actually match at runtime.
- **Real AWS costs.** AgentCore Runtime isn't free tier and teardown is a
  two-step CloudFormation dance, so `deploy.sh` defaults to idempotent, with
  `--dry-run`/`--diff` before anything touches billing.

## Accomplishments we're proud of

- An agent that *acts*, safely — not a chatbot that just talks about plans.
- Human-in-the-loop as a testable guardrail, verified against a live model,
  not just a polite system-prompt request.
- Two guardrails, two failure modes: a deterministic consent check plus an
  LLM check for tone and false completion claims.
- The discipline to delete our own mock-data layer once the real thing
  worked.

## What we learned

- **Human-in-the-loop is a design decision**, not a flag — the hard part was
  defining *which* actions need one and *what counts* as confirmation.
- **MCP makes real data trivial to wire in**; the real work is governing how
  the agent's allowed to use it.
- **A demo-only mock layer erodes trust** — better an honest Texas-only scope
  than quietly blended real and fabricated answers.
- **Deploying is its own discipline**: AgentCore's warm-container model
  changes how session state and cost behave versus local dev.

## What's next for Utility Bot

- **Beyond Texas** via broader or additional regional MCP sources.
- **A real budget estimate**, summing actual Utilify rates across services.
- **Post-enrollment follow-up** using `utilify_check_signup_status`.
- **Structured confirm/cancel UX**, not just a phrase match.
- **Multi-agent split** — shopping advisor and enrollment agent as separate
  agents, shrinking the enrollment agent's tool surface by construction.
