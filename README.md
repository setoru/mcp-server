# mcp-server

Huawei MCP Server is a Model Context Protocol server built on Huawei Cloud services, providing secure and controlled cloud access capabilities for large AI models. Through standardized MCP specifications, it enables AI assistants to operate Huawei Cloud resources within conversational workflows, supporting core services including ECS, OBS, GaussDB, and other widely-used cloud products.


# Prepare
Install uv

# On macOS and Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
Configuration
Use VS Code + Cline to config MCP Server.

To use huaweicloud-ecs-ops-mcp-server MCP Server with any other MCP Client, you can manually add this configuration and restart for changes to take effect:

{
  "mcpServers": {
    "huaweicloud-ecs-ops-mcp-server": {
      "timeout": 600,
      "command": "uv",
      "args": [
            "--directory",
            "/projects/lhw/hc_mcp_servers/mcp-server/src",
            "run",
            "server.py"
      ],
      "env": {
        "HUAWEI_CLOUD_AK": "Your Access Key AK",
        "HUAWEI_CLOUD_SK": "Your Access Key SK"
      }
    }
  }
}

# MCP Maketplace Integration
Cline

# Tools