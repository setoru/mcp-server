---
name: huawei-vpc-list-vpcs
description: Query Huawei Cloud VPCs and optionally inspect VPC details and subnets through Huawei Cloud VPC MCP tools. Use when checking VPC inventory, filtering by ID/name/CIDR, or confirming the VPC and subnet scope in a region and project.
compatibility: Prefers Huawei Cloud VPC MCP tools in the current environment. If they are unavailable but the repo-local VPC helper path is present, this skill may use that bounded fallback path instead. IAM and EPS MCP tools remain useful follow-ups for project and enterprise-project discovery.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: list-vpcs
---

# Huawei VPC List VPCs

## What this skill does

- Query VPC inventory with read-only VPC operations.
- Support narrow filters like `id`, `name`, `cidr`, and `description`.
- Confirm one VPC in detail and optionally inspect its subnets.
- Help avoid the common mistake of mixing the wrong `region` with the wrong `project_id`.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, `enterprise_project_id`, `vpc_id`, and `subnet_id` as defaults before proceeding. Apply any extracted value when the tool supports it and the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an API filter unless it has already been normalized to an exact resource name.

Primary tools:

- `huaweicloud-vpc_ListVpcs`
- `huaweicloud-vpc_ShowVpc`
- `huaweicloud-vpc_ListSubnets`
- `huaweicloud-vpc_ShowSubnet`

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-iam_KeystoneListProjects`
- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-iam_KeystoneListRegions`
- `huaweicloud-iam_KeystoneShowRegion`
- `huaweicloud-iam_KeystoneShowProject`
- `huaweicloud-eps_ListEnterpriseProject`

## Runtime fallback when required tools are unavailable

If the expected VPC MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local VPC execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/run.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/config.yaml`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/vpc.json`
- `huaweicloud_services_server/mcp_server_vpc_lite/src/mcp_server_vpc_lite/run.py`
- `huaweicloud_services_server/mcp_server_vpc_lite/src/mcp_server_vpc_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_vpc_lite/src/mcp_server_vpc_lite/config/vpc.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local VPC specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local VPC execution path can safely provide the required capability.

## Required inputs

- `project_id` (or enough region context to discover it with IAM first)

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `id`
- `name`
- `cidr`
- `description`
- `limit`
- `marker`
- `vpc_id` (when the user already knows the target VPC and wants subnet follow-up)
- `subnet_id` (when the user wants one subnet detail)

## Default workflow

1. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, `enterprise_project_id`, `vpc_id`, and `subnet_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is missing, prefer discovering it with `huaweicloud-iam_KeystoneListAuthProjects({ region })` before querying VPCs.
   - When discovering `project_id`, prefer the project whose name matches the target `region` exactly; if that still leaves ambiguity, say which project you picked.
   - Do not silently mix a `project_id` from one region with a different `region`.

2. Start with the VPC list call.
   - Call `huaweicloud-vpc_ListVpcs({ project_id, region, ...filters })`.
   - Prefer narrow filters like `id`, `name`, or `cidr` instead of a wide unfiltered inventory call.
   - If pagination is needed, continue with `marker` and `limit`.

3. Confirm a single VPC when needed.
   - If the list result returns one likely target, or the user already provided a `vpc_id`, call `huaweicloud-vpc_ShowVpc({ project_id, region, vpc_id })`.
   - Use this to confirm fields like `cidr`, `status`, tags, and returned `enterprise_project_id`.

4. Inspect subnets only after the VPC is known.
   - Prefer `huaweicloud-vpc_ListSubnets({ project_id, region, vpc_id })` instead of listing all subnets in the project.
   - If the user needs one subnet detail, call `huaweicloud-vpc_ShowSubnet({ project_id, region, subnet_id })`.

5. Treat enterprise project information carefully.
   - `enterprise_project_id` is useful for understanding resource ownership.
   - Do not assume `ListVpcs`, `ShowVpc`, `ListSubnets`, and `ShowSubnet` all support `enterprise_project_id` as a request filter.
   - If the user needs to discover enterprise projects first, use `huaweicloud-eps_ListEnterpriseProject(...)` as a separate helper step.

## Interpretation rules

- A successful `ListVpcs` response with zero VPCs is not an auth failure by itself; it can simply mean there are no VPCs in that region/project scope.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still fail or return nothing if the `region` is wrong.
- `ShowVpc` is better for final confirmation than for discovery.
- `ListSubnets` should usually be constrained by `vpc_id` to avoid noisy cross-VPC results.

## Safety and scope

- This skill is read-only.
- Do not create, update, or delete VPCs, subnets, routes, or security resources.
- Do not guess a different `project_id`, `region`, `vpc_id`, or `subnet_id` silently.
- Do not claim `enterprise_project_id` is a universal request filter for these VPC query calls unless the exact target API confirms it.

## Output checklist

1. region used
2. project used
3. filters applied
4. number of VPCs found
5. key VPC fields for each match
6. whether `ShowVpc`, `ListSubnets`, or `ShowSubnet` was used as follow-up
7. exact blocker if the query failed
8. execution path used: `mcp-tools` or `repo-helper`
