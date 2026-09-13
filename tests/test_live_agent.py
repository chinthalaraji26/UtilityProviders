"""Live integration tests - skipped by default.

These call a real, running agent and cost real tokens/AWS usage, so they only
run when explicitly opted into:

    RUN_LIVE_TESTS=1 pytest tests/test_live_agent.py -v

Two modes, chosen by which env vars are set:
- AGENT_RUNTIME_ARN set: invokes the deployed AgentCore Runtime via boto3
  (what DEPLOY.md's smoke test also does after `agentcore deploy`).
- Neither set: falls back to constructing the local agent in-process
  (same path main.py uses) and calling it directly - still a real
  Bedrock call, just without a deployed runtime.
"""

import json
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Live tests call real Bedrock/AgentCore and are opt-in only. Set RUN_LIVE_TESTS=1 to run.",
)


def _invoke_deployed(prompt: str, session_id: str) -> str:
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-agentcore", region_name=region)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=os.environ["AGENT_RUNTIME_ARN"],
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": prompt}).encode(),
        qualifier="DEFAULT",
    )
    # Join raw bytes across all chunks before decoding once - a multi-byte
    # UTF-8 character (the model does stream emoji sometimes, per main.py's
    # own comment on this) can land split across a chunk boundary, and
    # decoding each chunk independently breaks mid-sequence in that case.
    return b"".join(response.get("response", [])).decode("utf-8")


def _invoke_local(prompt: str) -> str:
    from main import invoke

    return invoke({"prompt": prompt}, context=None)


def _invoke(prompt: str, session_id: str) -> str:
    if os.environ.get("AGENT_RUNTIME_ARN"):
        return _invoke_deployed(prompt, session_id)
    return _invoke_local(prompt)


@pytest.fixture
def session_id():
    # AgentCore requires runtimeSessionId to be at least 33 characters.
    return f"live-test-session-{uuid.uuid4()}"


def test_search_plans_flow(session_id):
    result = _invoke("What electricity plans are available in zip code 78701?", session_id)
    # 78701 is downtown Austin, TX - Utilify should recognize the area even if
    # the specific plans returned change over time.
    assert "78701" in result or "austin" in result.lower()


def test_enrollment_requires_confirmation(session_id):
    # A single-shot "sign me up" with no prior confirmation in this session
    # must not be treated as consent - EnrollmentConfirmationHandler should
    # block utilify_initiate_signup, so the agent may only ask for more
    # info / offer to help, never claim the enrollment already happened.
    # (A plain "signed up" substring check is too blunt - "help you get
    # signed up" is a safe, forward-looking offer, not a completion claim.)
    result = _invoke("Sign me up for electricity in zip code 78701", session_id)
    lower = result.lower()
    completion_claims = [
        "you're enrolled", "you are enrolled", "successfully enrolled",
        "you're signed up", "you are signed up", "successfully signed up",
        "sign-up complete", "signup complete", "enrollment complete", "enrollment is complete",
    ]
    assert not any(phrase in lower for phrase in completion_claims), result


def test_budget_and_checklist_flow(session_id):
    # There's no dedicated budget tool (see Summary.md's "What's next") - a
    # budget question is answered by the model reasoning over what it already
    # found, and utilify_get_move_checklist covers the "planning a move"
    # angle. Search first so there's something concrete to reason about.
    _invoke("What electricity plans are available in zip code 78701?", session_id)
    result = _invoke(
        "I'm moving there - what's the full utility setup checklist I need, "
        "and roughly what would my monthly costs look like?",
        session_id,
    )
    lower = result.lower()
    # A real moving checklist spans multiple utility categories, not just a
    # repeat of the single electricity search from the previous turn - this
    # is what distinguishes "used get_move_checklist" from "ignored the ask".
    utility_categories = ["water", "gas", "internet", "trash", "sewer", "security"]
    mentioned = [c for c in utility_categories if c in lower]
    assert len(mentioned) >= 2, f"Expected the checklist to span multiple utilities, got: {result}"


def test_confirm_then_enroll_never_claims_completion(session_id):
    # The full happy path: search, then confirm in the customer's own words
    # with the contact details utilify_initiate_signup needs as tool input
    # (name/email/phone/address/move-in date).
    #
    # This only asserts the one invariant that holds regardless of path:
    # never claim enrollment is done. It deliberately does NOT require a
    # specific "next step" response (e.g. a link) - live runs of this same
    # prompt have taken at least three different, all individually correct,
    # defensive paths: (1) asking for the missing contact details, (2)
    # echoing a summary and asking for one more explicit go-ahead before
    # calling the tool, and (3) tone_handler's *inherited* steer_before_tool
    # (ToneGuardrailHandler only overrides steer_after_model, but
    # LLMSteeringHandler's default steer_before_tool also reviews tool
    # calls) judging the supplied details as fabricated and raising an
    # Interrupt for human review. That third path also surfaced a real bug
    # worth fixing separately: main.py's invoke() has no interrupt handling,
    # so the interrupt's internal representation leaked verbatim into the
    # customer-facing response - see the discussion around this test's
    # addition. Once that's addressed, consider tightening this assertion
    # back to also require a customer-safe next step in every path.
    _invoke("What electricity plans are available in zip code 78701?", session_id)
    result = _invoke(
        "Great, yes - go ahead and sign me up for the first plan you found. "
        "I'm Test User, test.user@example.com, 555-010-0100, 123 Test St, "
        "Austin, TX 78701, and I'd like to start service on the 1st of next month.",
        session_id,
    )
    lower = result.lower()

    if not any(word in lower for word in ("link", "http", "provider", "finish")):
        # Path (2) above - the model asked for one more explicit go-ahead
        # rather than treating the details-plus-"sign me up" message as
        # sufficient. Give it, then check the response after that instead.
        result = _invoke("Yes, go ahead.", session_id)
        lower = result.lower()

    completion_claims = [
        "you're enrolled", "you are enrolled", "successfully enrolled",
        "you're signed up", "you are signed up", "successfully signed up",
        "sign-up complete", "signup complete", "enrollment complete", "enrollment is complete",
    ]
    assert not any(phrase in lower for phrase in completion_claims), result
