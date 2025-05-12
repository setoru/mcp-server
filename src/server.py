from mcp.server.fastmcp import FastMCP

import logging

from tools import ecs_tools,vpc_tools

logger = logging.getLogger(__name__)


def main(transport: str):
    # Create an MCP server
    mcp = FastMCP("huawei-cloud-ops-mcp-server")
    for tool in ecs_tools.tools:
        mcp.add_tool(tool)
    
    for tool in vpc_tools.tools:
        mcp.add_tool(tool)
    
    # Initialize and run the server
    logger.debug(f'mcp server is running on {transport} mode.')
    mcp.run(transport=transport)



if __name__ == "__main__":
    main("stdio")