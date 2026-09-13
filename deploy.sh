#!/usr/bin/env bash
# Deploy the Movers Helper Agent to Amazon Bedrock AgentCore Runtime.
#
# Scaffolds an AgentCore CLI project (agentcore-project/MoversHelperAgent/), wires
# our source files in as a "Bring your own code" agent, and deploys it via
# `agentcore deploy` (which provisions an IAM execution role + a
# AWS::BedrockAgentCore::Runtime resource in your AWS account via CloudFormation).
# On a real deploy, also runs scripts/deploy_rate_limiter.py to provision the
# Lambda + DynamoDB table behind hooks.RateLimiterHook's cross-container mode -
# see that script's docstring and ARCHITECTURE.md.
#
# Safe to re-run: each step is skipped if its output already exists, except
# the actual `agentcore deploy` call, which always re-applies (that's how you
# push code changes to an existing deployment).
#
# Usage:
#   ./deploy.sh                 # scaffold + deploy
#   ./deploy.sh --dry-run       # scaffold, then preview the deploy without applying it
#   ./deploy.sh --diff          # scaffold, then show the CloudFormation diff
#   ./deploy.sh --teardown      # remove the deployed runtime from AWS
#
# Prerequisites: Node.js 20+, the `agentcore` CLI (npm i -g @aws/agentcore),
# `uv`, Python 3 with boto3 (requirements-deploy.txt) for the rate-limiter
# provisioning step, and AWS credentials with Bedrock + AgentCore +
# CloudFormation + DynamoDB + Lambda + IAM access.

set -euo pipefail

# Work around a Windows-specific uv bug: the CDK build stages Python deps
# into agentcore-project/.../agentcore/.cache/ by hardlinking from uv's
# global package cache. If either path is inside a cloud-synced folder
# (OneDrive, etc.), Windows' Cloud Files API rejects the hardlink with
# "os error 396: The cloud operation cannot be performed on a file with
# incompatible hardlinks." UV_LINK_MODE=copy makes uv copy instead of
# hardlink - slightly slower, always works. Harmless (and a no-op) on
# platforms that don't hit this. See:
# https://docs.astral.sh/uv/reference/environment/#uv_link_mode
export UV_LINK_MODE=copy

PROJECT_NAME="MoversHelperAgent"
AGENT_NAME="MoversHelperAgent"
PROJECT_DIR="agentcore-project/${PROJECT_NAME}"
APP_DIR="${PROJECT_DIR}/app/${AGENT_NAME}"
SOURCE_FILES=(main.py mcp_providers.py steering_handlers.py hooks.py)

mode="${1:-deploy}"

PYTHON_BIN=""

check_prereqs() {
    for cmd in node npm agentcore uv; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "Missing prerequisite: $cmd" >&2
            echo "See README.md / DEPLOY.md for install instructions." >&2
            exit 1
        fi
    done

    for cmd in python3 python; do
        # command -v only checks PATH, not that the binary actually runs - on
        # Windows, `python3` often resolves to a Microsoft Store shim that
        # exists on PATH but errors out instead of running, if no real
        # Python is installed under that name. Actually invoke it.
        if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c "" >/dev/null 2>&1; then
            PYTHON_BIN="$cmd"
            break
        fi
    done
    if [ -z "$PYTHON_BIN" ]; then
        echo "Missing prerequisite: a working python3/python (needed for scripts/deploy_rate_limiter.py)" >&2
        exit 1
    fi
}

scaffold_project() {
    if [ -d "$PROJECT_DIR" ]; then
        echo "== Project already scaffolded at $PROJECT_DIR, skipping create =="
        return
    fi
    echo "== Scaffolding AgentCore project =="
    agentcore create \
        --project-name "$PROJECT_NAME" \
        --no-agent --defaults --skip-git \
        --output-dir ./agentcore-project --json

    echo "== Installing CDK app dependencies (npm) =="
    (cd "$PROJECT_DIR/agentcore/cdk" && npm install)
}

sync_app_source() {
    echo "== Syncing agent source into $APP_DIR =="
    mkdir -p "$APP_DIR"
    cp "${SOURCE_FILES[@]}" "$APP_DIR/"
    rm -rf "$APP_DIR/skills"
    cp -r skills "$APP_DIR/skills"

    if [ ! -f "$APP_DIR/pyproject.toml" ]; then
        echo "== Initializing uv project for the deployable agent =="
        (cd "$APP_DIR" && uv init --bare --python 3.13)
        (cd "$APP_DIR" && uv add strands-agents bedrock-agentcore aws-opentelemetry-distro boto3)
    fi
}

is_agent_registered() {
    # A plain grep for "name": "$AGENT_NAME" would also match agentcore.json's
    # top-level project name (same field, same string when PROJECT_NAME and
    # AGENT_NAME match, as they do here) - check specifically inside the
    # "runtimes" array, where a registered agent's entry actually lives.
    "$PYTHON_BIN" -c "
import json, sys
try:
    with open('$PROJECT_DIR/agentcore/agentcore.json') as f:
        data = json.load(f)
except FileNotFoundError:
    sys.exit(1)
sys.exit(0 if any(r.get('name') == '$AGENT_NAME' for r in data.get('runtimes', [])) else 1)
"
}

register_agent() {
    if is_agent_registered; then
        echo "== Agent '$AGENT_NAME' already registered, skipping add =="
        return
    fi
    echo "== Registering the BYO agent =="
    (cd "$PROJECT_DIR" && agentcore add agent \
        --name "$AGENT_NAME" \
        --type byo --language Python --framework Strands --model-provider Bedrock \
        --code-location "app/${AGENT_NAME}" --entrypoint main.py --json)
}

deploy_rate_limiter() {
    # Provisions the Lambda + DynamoDB table hooks.RateLimiterHook can use for
    # cross-container rate limiting, and grants the just-deployed agent's
    # execution role permission to invoke it. Independent of the
    # agentcore-managed CDK app - see scripts/deploy_rate_limiter.py.
    echo "== Provisioning rate-limiter Lambda + DynamoDB table =="
    "$PYTHON_BIN" scripts/deploy_rate_limiter.py --project-dir "$PROJECT_DIR"
}

teardown_rate_limiter() {
    # Must run before `agentcore remove agent` / the teardown `agentcore
    # deploy` below: it strips the inline policy this adds to the agent's
    # execution role, and IAM refuses to delete a role that still has one.
    echo "== Removing rate-limiter Lambda + DynamoDB table =="
    "$PYTHON_BIN" scripts/deploy_rate_limiter.py --project-dir "$PROJECT_DIR" --teardown
}

main() {
    check_prereqs
    scaffold_project
    sync_app_source
    register_agent

    case "$mode" in
        --dry-run)
            echo "== Previewing deploy (no AWS changes) =="
            (cd "$PROJECT_DIR" && agentcore deploy --dry-run --json)
            ;;
        --diff)
            echo "== Showing CloudFormation diff (read-only) =="
            (cd "$PROJECT_DIR" && agentcore deploy --diff --json)
            ;;
        --teardown)
            teardown_rate_limiter
            echo "== Removing agent from local config =="
            (cd "$PROJECT_DIR" && agentcore remove agent --name "$AGENT_NAME" -y --json)
            echo "== Applying teardown to AWS =="
            (cd "$PROJECT_DIR" && agentcore deploy -y --json)
            ;;
        deploy)
            echo "== Deploying to AWS (this provisions billed resources) =="
            (cd "$PROJECT_DIR" && agentcore deploy -y --json)
            deploy_rate_limiter
            echo
            echo "== Deployed. Fetching status =="
            (cd "$PROJECT_DIR" && agentcore status --json)
            echo
            echo "Try it:  (cd $PROJECT_DIR && agentcore invoke \"What electricity plans are available in zip code 78701?\")"
            ;;
        *)
            echo "Unknown mode: $mode (expected: deploy, --dry-run, --diff, --teardown)" >&2
            exit 1
            ;;
    esac
}

main
