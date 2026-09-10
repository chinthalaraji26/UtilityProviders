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
    return "".join(chunk.decode("utf-8") for chunk in response.get("response", []))


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
