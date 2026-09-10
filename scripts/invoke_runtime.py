"""Invoke a deployed AgentCore Runtime agent, optionally continuing a session.

Requires the `boto3` dependency from requirements-deploy.txt and AWS
credentials with `bedrock-agentcore:InvokeAgentRuntime` access.

    $env:AGENT_RUNTIME_ARN = "<ARN from `agentcore status`>"
    $env:AWS_REGION = "us-east-1"   # optional, defaults to us-east-1
    python scripts/invoke_runtime.py "What providers are available in zip code 78701?"

Prints the session id it used to stderr - pass it back in with --session-id
to continue that same conversation. AgentCore Runtime keeps a session's
requests pinned to the same warm container, so the agent remembers prior
turns as long as you reuse the id:

    python scripts/invoke_runtime.py "Estimate my budget with those" --session-id <id from above>
"""

import argparse
import json
import os
import sys
import uuid

import boto3

# The model may stream emoji/special characters that some consoles' default
# encoding (e.g. Windows cp1252) can't print, which otherwise crashes the
# process mid-response. Force UTF-8 stdout so any character just prints
# correctly, on any platform.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument(
        "--session-id",
        default=None,
        help="Reuse a prior session id (printed on a previous run) to continue that conversation.",
    )
    args = parser.parse_args()

    arn = os.environ.get("AGENT_RUNTIME_ARN")
    if not arn:
        sys.exit("Set $env:AGENT_RUNTIME_ARN first - see `agentcore status` for the ARN.")
    region = os.environ.get("AWS_REGION", "us-east-1")
    # AgentCore requires runtimeSessionId to be at least 33 characters.
    session_id = args.session_id or f"{uuid.uuid4()}-{uuid.uuid4()}"

    client = boto3.client("bedrock-agentcore", region_name=region)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": args.prompt}).encode(),
        qualifier="DEFAULT",
    )
    result = "".join(chunk.decode("utf-8") for chunk in response["response"])

    print(result)
    print(f"\n--- session id (pass to --session-id to continue this conversation): {session_id} ---", file=sys.stderr)


if __name__ == "__main__":
    main()
