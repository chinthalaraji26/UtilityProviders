"""MCP tool provider(s) for the Movers Helper Agent.

Utilify (https://utilify.io) runs a public MCP server that searches and
compares real electricity, internet, gas, water, and trash plans for Texas
zip codes, and can kick off enrollment. No API key required.
Docs: https://utilify.io/mcp-docs

We prefix its tools with "utilify_" so it's unambiguous in logs, guardrails,
and the system prompt which server a tool call came from - this is currently
the agent's only tool source.

Exposed tools (after the "utilify_" prefix):
    utilify_search_utility_providers  - list providers for a Texas address
    utilify_get_provider_details      - pricing/terms/fees for one provider
    utilify_compare_providers         - side-by-side comparison (2-5 providers)
    utilify_initiate_signup           - returns a redirect link for the
                                         customer to finish enrollment
                                         themselves; never completes signup
                                         on its own (see steering_handlers.
                                         EnrollmentConfirmationHandler, which
                                         keeps a human in the loop before this
                                         tool - and utilify_request_solar -
                                         are allowed to run)
    utilify_check_signup_status       - poll a previously-initiated signup
    utilify_get_move_checklist        - personalized move-in utility checklist
    utilify_get_promotions            - current deals/bonuses for a zip code
    utilify_request_solar             - routes a rooftop solar inquiry to
                                         installers (shares the customer's
                                         contact info - also gated by
                                         EnrollmentConfirmationHandler)

Used by main.py. MCPClient implements Strands' ToolProvider interface, so
connect/disconnect lifecycle is managed automatically by the Agent - just
pass it in the `tools=[...]` list like any other tool.
"""

from strands.tools.mcp import MCPClient

UTILIFY_MCP_URL = "https://utilify.io/mcp"

utilify_tools = MCPClient(url=UTILIFY_MCP_URL, prefix="utilify")
