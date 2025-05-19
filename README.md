# mcp-server
[![GitHub License](https://img.shields.io/github/license/manusa/kubernetes-mcp-server)](https://github.com/manusa/kubernetes-mcp-server/blob/main/LICENSE)
[![CI](https://github.com/HuaweiCloudDeveloper/mcp-server/actions/workflows/lint.yaml/badge.svg)](https://github.com/HuaweiCloudDeveloper/mcp-server/actions/workflows/lint.yaml) 
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/HuaweiCloudDeveloper/mcp-server/pulls)
[![Last Commit](https://img.shields.io/github/last-commit/HuaweiCloudDeveloper/mcp-server)](https://github.com/HuaweiCloudDeveloper/mcp-server/commits/main) 
[![Language](https://img.shields.io/github/languages/top/HuaweiCloudDeveloper/mcp-server)](https://github.com/HuaweiCloudDeveloper/mcp-server)

Huawei MCP Server is a Model Context Protocol server built on Huawei Cloud services, providing secure and controlled cloud access capabilities for large AI models. Through standardized MCP specifications, it enables AI assistants to operate Huawei Cloud resources within conversational workflows, supporting core services including ECS, OBS, GaussDB, and other widely-used cloud products.

## Demo

[Demo](https://github.com/HuaweiCloudDeveloper/mcp-server/blob/main/media/mcp-server-demo.mp4](https://private-user-images.githubusercontent.com/131579790/444946169-caf942b7-c3fa-496b-b99a-30a2d7c703e9.mp4?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NDc2MjA1MDUsIm5iZiI6MTc0NzYyMDIwNSwicGF0aCI6Ii8xMzE1Nzk3OTAvNDQ0OTQ2MTY5LWNhZjk0MmI3LWMzZmEtNDk2Yi1iOTlhLTMwYTJkN2M3MDNlOS5tcDQ_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUwNTE5JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDUxOVQwMjAzMjVaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT0wNWRlNTdhMmJmZGQ5YTM1NDU3YjE5NDk1ZGRlNmE4MjU4ZWE0ODMxODFmNDVlYjc2NWVkNGIxZGEzODU1NWZjJlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.llprhwT5fsddo9_NlSF14EjrGgIyFt4RQjVErUiRyV4)

The video demonstrates using Cline with Huawei MCP Server to create a new ECS instance and remove it.

## Prepare
Install [uv](https://github.com/astral-sh/uv)

```sh
# On macOS and Linux.
 curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Configuration
Use [VS Code](https://code.visualstudio.com/) + [Cline](https://cline.bot/) to config MCP Server.

To use huaweicloud-ecs-ops-mcp-server MCP Server with any other MCP Client, you can manually add this configuration and restart for changes to take effect:

```json
{
  "mcpServers": {
    "huaweicloud-ecs-ops-mcp-server": {
      "timeout": 600,
      "command": "uv",
      "args": [
            "--directory",
            "/path/to/yours/mcp-server/src",
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
```
## MCP Maketplace Integration

* [Cline](https://cline.bot/mcp-marketplace)

## Tools

| **Product** | **Tool** | **Function**                  | **Implematation** | **Status** |
| --- | --- |-------------------------------|-------------------| --- |
| ECS | create_post_paid_ecs_instance | Create post paid ecs instance | ECS               | Done |
| | delete_ecs_instance | Delete ecs instance         | ECS               | Done |
| | select_ecs_instance | Retrieve ecs instance | ECS               | Done |
| VPC | get_vpc_id | Get vpc id     | VPC               | Done |
| | list_all_subnets | list all subnets              | VPC               | Done |
| | get_subnet_id | Get subnet id              | VPC               | Done |
| OBS | bucket_exist | Checks if a specified bucket exists | OBS               | Done |
|  | get_buckets | Get buckets                | OBS               | Done |
|  | delete_bucket | Delete bucket                 | OBS               | Done |
|  | create_bucket | Create bucket                 | OBS               | Done |
|  | get_objects | Get objects in the bucket     | OBS               | Done |
|  | download_object | Download object               | OBS               | Done |
|  | delete_object | Delete object                 | OBS               | Done |
