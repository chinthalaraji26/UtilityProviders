"""Shared hooks for the Movers Helper Agent.

Used by the main.py entrypoint.
"""

import json
import logging
import uuid

from strands.hooks import (
    HookProvider, HookRegistry,
    BeforeInvocationEvent, BeforeToolCallEvent,
)

logger = logging.getLogger(__name__)

# Fixed, well-known name for the rate limiter's backing Lambda function -
# provisioned by scripts/deploy_rate_limiter.py. Both that script and
# RateLimiterHook just agree on this name, so no wiring (env vars, config
# files) is needed between deploy.sh and the deployed agent's own code to
# tell it where the Lambda lives. See ARCHITECTURE.md.
RATE_LIMITER_LAMBDA_NAME = "MoversHelperAgentRateLimiter"

# Lambda invoke calls block a tool call from running, so keep the timeout
# short - a slow rate-limit check shouldn't make the whole agent turn feel
# stuck. Combined with fail-open (see class docstring), a hung Lambda costs
# a customer at most this long once per turn, not a stalled response.
_LAMBDA_INVOKE_TIMEOUT_SECONDS = 2


class RateLimiterHook(HookProvider):
    """Caps each tool at max_calls per agent invocation (one user turn).

    By default (lambda_function_name=None) counting happens in-process, in
    an in-memory dict. That's correct only as long as one turn's tool calls
    all land on the same container - true today, but AgentCore Runtime's
    warm-container model means a customer's calls aren't guaranteed to stay
    on one container forever, so an in-memory count isn't a real limit
    across containers.

    Pass lambda_function_name to instead have a Lambda function (backed by
    DynamoDB, see lambdas/rate_limiter/handler.py) do the counting - one
    shared count regardless of which container is handling the request.
    This is deliberately fail-open: if that Lambda call ever errors or
    times out (not deployed, throttled, cold-starting, network blip), the
    tool call is allowed and the failure is logged, rather than blocking a
    customer over infra trouble. A side effect worth knowing: if the Lambda
    fails partway through a turn, remaining calls in that turn fall back to
    a fresh local count (starting from 0, not from the Lambda's last known
    count) - the limit becomes best-effort for the rest of that turn rather
    than exact, which is the trade-off fail-open implies.
    """

    def __init__(
        self,
        max_calls: int = 4,
        lambda_function_name: str | None = None,
        lambda_client=None,
    ):
        self.max_calls = max_calls
        self.lambda_function_name = lambda_function_name
        self.counts: dict[str, int] = {}
        self.invocation_id: str | None = None
        self._lambda_client = lambda_client
        self._lambda_unavailable = False  # set once this turn's Lambda call has failed

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.reset)
        registry.add_callback(BeforeToolCallEvent, self.check)

    def reset(self, event: BeforeInvocationEvent) -> None:
        """Reset counts at the start of each invocation."""
        self.counts = {}
        self.invocation_id = uuid.uuid4().hex
        self._lambda_unavailable = False  # give the Lambda a fresh chance each turn

    def check(self, event: BeforeToolCallEvent) -> None:
        """Check and enforce the rate limit before each tool call."""
        name = event.tool_use["name"]

        count = self._check_via_lambda(name) if self.lambda_function_name else None
        if count is None:
            self.counts[name] = self.counts.get(name, 0) + 1
            count = self.counts[name]

        if count > self.max_calls:
            event.cancel_tool = (
                f"'{name}' hit the {self.max_calls}-call limit for this turn. "
                "Do NOT call this tool again - answer with what you already have."
            )
            print(f"[HOOK] BLOCKED: {name} exceeded {self.max_calls} calls this turn!")

    def _check_via_lambda(self, tool_name: str) -> int | None:
        """Ask the rate-limiter Lambda for this tool's shared count this turn.

        Returns None (caller falls back to local, per-container counting for
        this call) if the Lambda is unreachable or errors - see class
        docstring on why that's fail-open rather than fail-closed.
        """
        if self._lambda_unavailable:
            return None
        try:
            response = self._get_lambda_client().invoke(
                FunctionName=self.lambda_function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "invocation_id": self.invocation_id,
                    "tool_name": tool_name,
                    "max_calls": self.max_calls,
                }).encode(),
            )
            if response.get("FunctionError"):
                raise RuntimeError(f"Lambda returned FunctionError: {response['FunctionError']}")
            payload = json.loads(response["Payload"].read())
            return int(payload["count"])
        except Exception:
            logger.warning(
                "Rate-limiter Lambda '%s' unreachable - falling back to local, "
                "per-container counting for the rest of this turn.",
                self.lambda_function_name,
                exc_info=True,
            )
            self._lambda_unavailable = True
            return None

    def _get_lambda_client(self):
        if self._lambda_client is None:
            import boto3
            from botocore.config import Config

            self._lambda_client = boto3.client(
                "lambda",
                config=Config(
                    connect_timeout=_LAMBDA_INVOKE_TIMEOUT_SECONDS,
                    read_timeout=_LAMBDA_INVOKE_TIMEOUT_SECONDS,
                    retries={"max_attempts": 1},
                ),
            )
        return self._lambda_client
