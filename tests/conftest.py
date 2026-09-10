"""Pytest configuration: make the project root importable from tests/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):
    # strands-agents' MCP client (strands.tools.mcp.mcp_client) still calls
    # the mcp package's now-deprecated streamablehttp_client() internally -
    # that's a strands-agents implementation detail, not something
    # mcp_providers.py or any of our own code calls. Registered as an
    # ini-level filter (not a plain warnings.filterwarnings() call) because
    # pytest resets the warning filters per test from its own filterwarnings
    # config - a module-level call here would get wiped out before each
    # test runs. Filters just this known, third-party warning rather than
    # silencing DeprecationWarning broadly, so a real one elsewhere still
    # surfaces. Safe to remove once strands-agents updates its internal call
    # to mcp's replacement streamable_http_client().
    config.addinivalue_line(
        "filterwarnings",
        r"ignore:Use .streamable_http_client. instead\.:DeprecationWarning",
    )
