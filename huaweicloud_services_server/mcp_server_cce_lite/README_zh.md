# CCE MCP Server (Lite)


## 版本
v0.1.0

## 简介

CCE MCP Server (Lite) 是一个精简版的 Model Context Protocol (MCP) Server，提供 MCP 客户端（如 Claude Desktop、Cline、Cursor）与华为云 CCE (云容器引擎) 服务交互的能力。基于自然语言即可完成 CCE 集群的核心管理操作。

## 可用工具

<html>
    <head></head>
    <body>
        <table border="1" cellspacing="0" cellpadding="5">
            <tbody>
                <tr>
                    <th>类别</th>
                    <th>工具名称</th>
                    <th>功能描述</th>
                    <th>状态</th>
                </tr>
                <tr>
                    <td rowspan="4">集群管理</td>
                    <td>ListClusters</td>
                    <td>获取指定项目下所有集群的详细信息。</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td>ShowCluster</td>
                    <td>获取指定集群的详细信息。</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td>HibernateCluster</td>
                    <td>集群休眠，将运行中的集群置于休眠状态，休眠后将不再收取控制节点资源费用。</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td>AwakeCluster</td>
                    <td>集群唤醒，唤醒已休眠的集群，唤醒后将继续收取控制节点资源费用。</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td rowspan="1">节点管理</td>
                    <td>ListNodes</td>
                    <td>获取集群下所有节点的详细信息。</td>
                    <td>To be tested</td>
                </tr>
                <tr>
                    <td rowspan="1">集群创建</td>
                    <td>CreateCluster</td>
                    <td>创建一个空集群（即只有控制节点Master，没有工作节点Node）。</td>
                    <td>To be tested</td>
                </tr>
            </tbody>
        </table>
    </body>
</html>

## 使用方法

### 前置条件
- 拥有华为云账号
- 已获取 AK/SK 凭证

### 配置

在 `config/config.yaml` 中配置传输方式和端口：

```yaml
service_code: cce
transport: http  # 支持 stdio, http 和 sse
port: 8888 # http 和 sse 模式需要设定端口
```

### 运行

```bash
python -m mcp_server_cce_lite.run
```
