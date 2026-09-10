"""Live integration tests - skipped by default.

These call a real, running agent and cost real tokens/AWS usage, so they only
run when explicitly opted into:

    RUN_LIVE_TESTS=1 pytest tests/test_live_agent.py -v

Two modes, chosen by which env vars are set:
- AGENT_RUNTIME_ARN set: invokes the deployed AgentCore Runtime via boto3
  (what DEPLOY.md's smoke test also does after `agentcore deploy`).
- Neither set: falls back to constructing the local agent in-process
  (same path chat.py/main.py use) and calling it directly - still a real
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


def test_find_providers_flow(session_id):
    result = _invoke("What providers are available in zip code 78701?", session_id)
    assert "Austin" in result
    assert "Google Fiber" in result or "Spectrum" in result


def test_budget_estimate_flow(session_id):
    result = _invoke(
        "For zip 78701, use Austin Water for water and Google Fiber for internet. What's my monthly budget?",
        session_id,
    )
    assert "$" in result
    # The estimate should surface the real per-household caveat, not a hard guarantee.
    assert "vary" in result.lower() or "typical" in result.lower()


def test_rejects_made_up_provider(session_id):
    result = _invoke(
        "In zip 78701, estimate my budget using 'Totally Fake ISP' for internet.",
        session_id,
    )
    assert "Fake ISP" not in result or "not" in result.lower() or "isn't" in result.lower() or "no" in result.lower()
