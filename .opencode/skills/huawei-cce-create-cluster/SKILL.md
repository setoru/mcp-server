---
name: huawei-cce-create-cluster
description: Create a Huawei Cloud CCE cluster through the built-in CCE MCP tools. Use when the user explicitly wants to create one cluster and already knows the target network and core cluster settings.
compatibility: Prefers Huawei Cloud CCE MCP tools in the current environment. If they are unavailable but the repo-local CCE helper path is present, this skill may use that bounded fallback path instead. IAM and VPC MCP tools remain useful follow-ups for project and network discovery.
metadata:
  domain: huaweicloud
  service: cce
  purpose: create-cluster
---

# Huawei CCE Create Cluster

## What this skill does

- Create exactly one CCE cluster.
- Stop after the create call returns.
- Report the returned cluster identifier, job identifier, and status information if present.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, `vpc_id`, `subnet_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
Do not assume scope defaults are sufficient for cluster creation unless the required create fields are still explicit and unambiguous.

Primary tools:

- `huaweicloud-cce_CreateCluster`

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-vpc_ListVpcs`
- `huaweicloud-vpc_ShowVpc`
- `huaweicloud-vpc_ListSubnets`
- `huaweicloud-vpc_ShowSubnet`

## Runtime fallback when required tools are unavailable

If the expected CCE MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local CCE execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/run.py`
- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/config/config.yaml`
- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/config/cce.json`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/run.py`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/config/cce.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local CCE specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local CCE execution path can safely provide the required capability.

## Required inputs

- `project_id`
- `metadata.name`
- `spec.flavor`
- `spec.hostNetwork.vpc`
- `spec.hostNetwork.subnet`
- `spec.containerNetwork.mode`

Additional required inputs for ENI / Turbo-style creation:

- `spec.eniNetwork.eniSubnetId`
- `spec.eniNetwork.subnets`

Strongly recommended inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `spec.version`
- `spec.serviceNetwork.IPv4CIDR`
- `spec.containerNetwork.cidr` or `spec.containerNetwork.cidrs`
- `spec.type`
- `metadata.alias`
- `spec.description`

## Default workflow

1. Confirm the user explicitly wants to create a cluster.
   - This skill is for an intentional create action, not for planning only.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, `vpc_id`, `subnet_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before creation.

3. Require all creation inputs explicitly.
   - If `metadata.name`, `spec.flavor`, `spec.hostNetwork.vpc`, `spec.hostNetwork.subnet`, or `spec.containerNetwork.mode` is missing, ask for the missing field.
   - If `spec.containerNetwork.mode` is `eni`, require the ENI subnet fields explicitly.
   - Do not guess VPC IDs, network IDs, cluster flavor values, Kubernetes version, or container/service CIDRs.

4. Call the create tool once using the MCP tool schema.
   - `huaweicloud-cce_CreateCluster({ apiVersion: "v3", kind: "Cluster", project_id, region, metadata, spec })`

5. Stop after the create result.
   - Report the returned cluster ID, job ID, phase, and message fields if present.

## Interpretation rules

- `hostNetwork.subnet` is not the same as an ENI subnet identifier; do not silently substitute one for the other.
- `CreateCluster` creates an empty cluster control plane; it does not automatically create worker nodes.
- Omitting `spec.version` can let the platform choose a newer default than the user expected.
- A successful create response can still represent an asynchronous job; report that state instead of claiming the cluster is fully ready.

## Safety and scope

- This skill performs one mutating action.
- Do not auto-create nodes, node pools, NAT gateways, security groups, or follow-up network resources.
- Do not normalize fuzzy names into exact IDs without confirming them first.
- Do not chain follow-up mutations.

## Output checklist

1. region used
2. project used
3. essential create payload fields actually sent
4. returned cluster ID
5. returned job ID or phase if present
6. exact blocker if creation could not proceed
7. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
