"""A minimal real MCP server, used to test live tool discovery against an
actual stdio server rather than a mock.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fake-server")


@mcp.tool()
def ping() -> str:
    """Return pong."""
    return "pong"


@mcp.tool()
def echo(text: str) -> str:
    """Echo the given text back."""
    return text


if __name__ == "__main__":
    mcp.run(transport="stdio")
