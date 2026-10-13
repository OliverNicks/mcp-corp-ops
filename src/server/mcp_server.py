"""FastMCP Server Entrypoint for Corporate Agent Platform."""
import argparse
import sys
from fastmcp import FastMCP

# 1. Initialize FastMCP server instance
mcp = FastMCP(
    name="corporate-agent-platform",
    dependencies=["pydantic", "sqlalchemy", "redis", "sqlglot"],
)

# 2. Register sample / core tools
@mcp.tool()
def health_check() -> dict[str, str]:
    """Return platform operational status."""
    return {"status": "ok", "service": "corporate-agent-platform"}


# 3. CLI entrypoint supporting both STDIO (Claude Desktop) and SSE/HTTP (K8s/Docker)
def main() -> None:
    parser = argparse.ArgumentParser(description="Corporate Agent FastMCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol: 'stdio' for desktop clients, 'sse' for HTTP/container deployments",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host for SSE")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port for SSE")

    args = parser.parse_args()

    if args.transport == "sse":
        print(
            f"Starting FastMCP SSE server on {args.host}:{args.port}...",
            file=sys.stderr,
        )
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        # Default stdio transport for Claude Desktop / CLI clients
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()