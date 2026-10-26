"""FastMCP Server Entrypoint for Corporate Agent Platform."""

import argparse
import logging
import os
import sys

from fastmcp import FastMCP

from src.core.config import settings
from src.core.telemetry import start_metrics_server
from src.server.tools.catalog_tool import register_catalog_tools
from src.server.tools.sales_tool import register_sales_tools
from src.server.tools.sql_tool import register_sql_tools

log_level = os.getenv("LOG_LEVEL", "INFO").upper()

# Explicitly configure basicConfig
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
    force=True,
)
# Create a module-specific logger instance
logger = logging.getLogger("mcp_server")

# Initialize FastMCP server instance
logger.debug("Creating FastMCP instance: name='corporate-agent-platform'")
mcp = FastMCP(name="corporate-agent-platform")


# 2. Register sample / core tools
@mcp.tool()
def health_check() -> dict[str, str]:
    """Return platform operational status."""
    # INFO: Claude invoked this tool
    logger.info("Tool 'health_check' invoked")

    payload = {"status": "ok", "service": "corporate-agent-platform"}

    # DEBUG: Exact payload returned to Claude
    logger.debug("Health check result: %s", payload)
    return payload


# Register domain tools
register_catalog_tools(mcp)
register_sales_tools(mcp)
register_sql_tools(mcp)


# 3. CLI entrypoint supporting both STDIO (Claude Desktop) and SSE/HTTP (K8s/Docker)
def main() -> None:
    parser = argparse.ArgumentParser(description="Corporate Agent FastMCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=settings.mcp_transport,
        help="Transport protocol: 'stdio' for desktop clients, 'sse' for HTTP/container deployments",
    )
    parser.add_argument("--host", default=settings.mcp_host, help="HTTP host for SSE")
    parser.add_argument("--port", type=int, default=settings.mcp_port, help="HTTP port for SSE")

    args = parser.parse_args()

    # DEBUG: Show parsed arguments
    logger.debug(
        "Parsed CLI arguments: transport=%s, host=%s, port=%s", args.transport, args.host, args.port
    )

    if args.transport == "sse":
        # INFO: High-level milestone for network services
        start_metrics_server(settings.metrics_port)
        logger.info("Starting FastMCP SSE server on http://%s:%d", args.host, args.port)
        if __name__ == "__main__":
            # If using args parsing:
            mcp.run(
                transport="sse",  # or "http" depending on your transport choice
                host=args.host,
                port=args.port,
            )
    else:
        # INFO: Milestone for desktop integrations
        logger.info("Starting FastMCP server over STDIO transport (Claude Desktop mode)...")
        # Default stdio transport for Claude Desktop / CLI clients
        mcp.run(transport="stdio")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server terminated by user (KeyboardInterrupt)")
    except Exception:
        # Captures any fatal startup crash and routes the full traceback to stderr
        logger.exception("Fatal error during MCP server execution")
        sys.exit(1)
