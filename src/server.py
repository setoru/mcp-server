import click
import logging
from mcp.config import config
from mcp.server import api_tools
from mcp.server.fastmcp import FastMCP

from tools import ecs_tools

logger = logging.getLogger(__name__)

# Create an MCP server
mcp = FastMCP("HuaweiCloud-ECS-ops-mcp-server")


@mcp.tool()
@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
def main(transport: str):
    # Create an MCP server
    mcp = FastMCP("alibaba-cloud-ops-mcp-server")
    for tool in ecs_tools.tools:
        mcp.add_tool(tool)

    api_tools.create_api_tools(mcp, config)

    # Initialize and run the server
    logger.debug(f'mcp server is running on {transport} mode.')
    mcp.run(transport=transport)
    logger.debug(f"mcp server is running on {transport} mode.")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
