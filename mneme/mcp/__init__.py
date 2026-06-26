"""mneme's advisory MCP server (read-only).

Serves recommendations (target config), honest status, campaign inventory, and the
on-demand management instructions / per-campaign usage guide. All mutation stays in
the `mneme mp` CLI behind preview-then-apply, so this server is never a runtime
dependency (Principle IV/VI).
"""
