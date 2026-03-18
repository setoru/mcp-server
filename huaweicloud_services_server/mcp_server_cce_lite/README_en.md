# CCE MCP Server (Lite)


## Version
v0.1.0

## Overview

CCE MCP Server (Lite) is a lightweight Model Context Protocol (MCP) server, providing the ability for MCP clients (such as Claude Desktop, Cline, Cursor) to interact with Huawei Cloud CCE (Cloud Container Engine) service. Core CCE cluster management operations can be carried out based on natural language.

## Available Tools

<html>
    <head></head>
    <body>
        <table border="1" cellspacing="0" cellpadding="5">
            <tbody>
                <tr>
                    <th>Category</th>
                    <th>Tool Name</th>
                    <th>Description</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td rowspan="4">Cluster Management</td>
                    <td>ListClusters</td>
                    <td>List all clusters under the specified project.</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td>ShowCluster</td>
                    <td>Get detailed information of a specified cluster.</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td>HibernateCluster</td>
                    <td>Hibernate a running cluster. After hibernation, control node resource fees will no longer be charged.</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td>AwakeCluster</td>
                    <td>Wake up a hibernated cluster. After waking up, control node resource fees will resume.</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td rowspan="1">Node Management</td>
                    <td>ListNodes</td>
                    <td>List all nodes under a specified cluster.</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td rowspan="1">Cluster Creation</td>
                    <td>CreateCluster</td>
                    <td>Create an empty cluster (with only control nodes, no worker nodes).</td>
                    <td>To be tested</td>
                </tr>
            </tbody>
        </table>
    </body>
</html>

## Usage

### Prerequisites
- A Huawei Cloud account
- AK/SK credentials obtained

### Configuration

Configure the transport mode and port in `config/config.yaml`:

```yaml
service_code: cce
transport: http  # Supports stdio, http, and sse
port: 8888 # Required for http and sse modes
```

### Run

```bash
python -m mcp_server_cce_lite.run
```
