"""Unit tests for main.py's invoke() entrypoint (payload parsing only).

get_agent() is monkeypatched to a stub so these run without AWS credentials
or a live model call - they only exercise the payload-unwrapping logic that
AgentCore Runtime's actual request shape needs.
"""

import pytest

import main


class StubAgent:
    def __init__(self):
        self.last_prompt = None

    def __call__(self, prompt):
        self.last_prompt = prompt
        return f"echo: {prompt}"


@pytest.fixture(autouse=True)
def stub_agent(monkeypatch):
    agent = StubAgent()
    monkeypatch.setattr(main, "get_agent", lambda: agent)
    return agent


def test_invoke_with_plain_string_prompt(stub_agent):
    result = main.invoke({"prompt": "What providers are in 78701?"}, context=None)
    assert result == "echo: What providers are in 78701?"


def test_invoke_unwraps_json_encoded_prompt(stub_agent):
    import json

    payload = {"prompt": json.dumps({"prompt": "Estimate my budget"})}
    result = main.invoke(payload, context=None)
    assert result == "echo: Estimate my budget"
    assert stub_agent.last_prompt == "Estimate my budget"


def test_invoke_raises_on_missing_prompt():
    with pytest.raises(ValueError, match="Missing required field"):
        main.invoke({}, context=None)


def test_invoke_raises_on_empty_prompt():
    with pytest.raises(ValueError, match="Missing required field"):
        main.invoke({"prompt": ""}, context=None)
