"""Unit tests for the parts of scripts/deploy_rate_limiter.py that don't
require AWS credentials or network access - packaging the Lambda zip and the
manual-grant fallback message. The AWS-calling functions (ensure_table,
ensure_lambda_function, grant_agent_invoke_permission, etc.) are exercised
manually against a real account when actually deploying; they're thin wraps
around documented boto3 calls, not logic worth mocking out here.
"""

import io
import zipfile

from scripts.deploy_rate_limiter import (
    RATE_LIMITER_LAMBDA_NAME,
    AGENT_POLICY_NAME,
    build_zip,
    manual_grant_instructions,
)


def test_build_zip_contains_just_the_handler():
    zip_bytes = build_zip()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert zf.namelist() == ["handler.py"]
        source = zf.read("handler.py").decode()
        assert "def handler(" in source


def test_manual_grant_instructions_name_the_function_and_policy():
    message = manual_grant_instructions("arn:aws:lambda:us-east-1:123456789012:function:Foo")
    assert RATE_LIMITER_LAMBDA_NAME in message
    assert AGENT_POLICY_NAME in message
    assert "arn:aws:lambda:us-east-1:123456789012:function:Foo" in message
