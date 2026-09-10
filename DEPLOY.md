# Deploying to Amazon Bedrock AgentCore Runtime

Deploys `main.py` (the same agent as `chat.py` - tools, rate-limiter hook,
skills, and steering guardrails, minus local file-based session persistence)
to **Amazon Bedrock AgentCore Runtime**, a managed, serverless runtime for
hosting agents.

## What this creates in your AWS account

Running the real deploy provisions, via CloudFormation (through the AgentCore CDK construct):

| Resource                         | Purpose                                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `AWS::IAM::Role` (+ policy)      | Execution role for the runtime - scoped to Bedrock model invocation, CloudWatch Logs, X-Ray, and AgentCore config bundles |
| `AWS::BedrockAgentCore::Runtime` | The hosted agent runtime itself                                                                                           |

Code is packaged as a zip (Direct Code Deploy / `CodeZip` - no container) and
uploaded to the CDK bootstrap staging bucket already in your account; no new
S3 bucket is created for this stack. **This costs money**: Bedrock model
inference charges apply per invocation, plus AgentCore Runtime's own hosting
charges. Nothing here is free-tier-guaranteed - check current
[AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/) before deploying.

## Prerequisites

- **Node.js 20+** and the AgentCore CLI: `npm install -g @aws/agentcore`
- **uv** ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **AWS credentials** with Bedrock, AgentCore, IAM, and CloudFormation access, and the account/region already [CDK-bootstrapped](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) (one-time per account/region; `deploy.sh` does not do this for you)
- Do **not** have `bedrock-agentcore-starter-toolkit` installed - it ships an older, conflicting `agentcore` CLI

## How do I deploy it?

```bash
./deploy.sh              # scaffold the AgentCore project, then deploy for real
./deploy.sh --dry-run    # scaffold, then preview the deploy - makes NO AWS changes
./deploy.sh --diff       # scaffold, then show the CloudFormation diff - read-only
./deploy.sh --teardown   # remove the deployed runtime from AWS
```

The script is idempotent for the scaffolding steps (skips work already done)
but always re-applies on `deploy` - that's how you push a code change to an
already-deployed agent. It:

1. Runs `agentcore create` to scaffold `agentcore-project/UtilProviders/` (a CDK app the CLI manages - gitignored, regenerate anytime with this script).
2. Copies `main.py`, `utility_provider_tools.py`, `steering_handlers.py`, `hooks.py`, and `skills/` into `agentcore-project/UtilProviders/app/UtilityAgent/`.
3. Runs `uv init` / `uv add` in that folder to produce the `pyproject.toml` the CodeZip build needs.
4. Runs `agentcore add agent` to register it as a "Bring your own code" Strands agent on Bedrock.
5. Runs `agentcore deploy -y` to synthesize and apply the CloudFormation stack.

### Invoke it

```bash
cd agentcore-project/UtilProviders
agentcore invoke "What providers are available in zip code 78701?"

# Keep context across calls with --session-id (must be >= 33 characters)
agentcore invoke --session-id utility-customer-session-000001 "I want Google Fiber for internet - what's my budget?"
```

### Invoke from code (boto3)

`agentcore invoke` is for testing; call the runtime directly in production:

```python
import json, uuid, boto3

client = boto3.client("bedrock-agentcore", region_name="us-east-1")
response = client.invoke_agent_runtime(
    agentRuntimeArn="<ARN from `agentcore status`>",
    runtimeSessionId=str(uuid.uuid4()),
    payload=json.dumps({"prompt": "What providers are available in zip code 78701?"}).encode(),
    qualifier="DEFAULT",
)
print("".join(chunk.decode("utf-8") for chunk in response.get("response", [])))
```

### Check status and logs

```bash
cd agentcore-project/UtilProviders
agentcore status
agentcore logs
```

## Running the live smoke tests against it

`tests/test_live_agent.py` is opt-in (skipped by default - it calls a real
model). Point it at your deployed runtime:

```bash
export AGENT_RUNTIME_ARN="<ARN from agentcore status>"
export AWS_REGION="us-east-1"
RUN_LIVE_TESTS=1 pytest tests/test_live_agent.py -v
```

Omit `AGENT_RUNTIME_ARN` and it falls back to calling the agent in-process
(still a real Bedrock call, just without a deployed runtime) - useful for
checking `main.py` itself before you deploy.

## Cleanup

```bash
./deploy.sh --teardown
```

This removes the agent from the local project config, then re-applies the
(now-empty) deploy so CloudFormation deletes the runtime and its IAM role -
mirroring the workshop's two-step `agentcore remove all -y` + `agentcore deploy` cleanup.
