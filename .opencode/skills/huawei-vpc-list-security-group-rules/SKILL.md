---
name: huawei-vpc-list-security-group-rules
description: Query Huawei Cloud security group rules and optionally inspect one rule in detail through Huawei Cloud VPC MCP tools. Use when checking current inbound or outbound exposure, filtering by exact rule IDs or security group scope, or confirming one rule in a resolved region and project.
compatibility: Prefers Huawei Cloud VPC MCP tools in the current environment. If they are unavailable but the repo-local VPC helper path is present, this skill may use that bounded fallback path instead. IAM MCP tools remain useful follow-ups for project discovery.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: list-security-group-rules
---

# Huawei VPC List Security Group Rules

## What this skill does

- Query security group rules with read-only VPC operations.
- Support narrow filters like `id`, `security_group_id`, `direction`, `protocol`, and remote-peer selectors.
- Confirm one rule in detail when the target rule is already known.
- Help avoid noisy project-wide enumeration when one security group or one rule ID is already available.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the tool supports it and the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an API filter unless it has already been normalized to an exact resource name.

Primary tools:

- `huaweicloud-vpc_ListSecurityGroupRules`
- `huaweicloud-vpc_ShowSecurityGroupRule`

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-iam_KeystoneListProjects`
- `huaweicloud-iam_KeystoneShowProject`

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
- `security_group_id`
- `direction`
- `action`
- `protocol`
- `ethertype`
- `enabled`
- `priority`
- `remote_ip_prefix`
- `remote_group_id`
- `remote_address_group_id`
- `description`
- `limit`
- `marker`
- `security_group_rule_id` (when the user already knows the target rule and wants one detail lookup)

## Default workflow

1. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is missing, prefer discovering it with `huaweicloud-iam_KeystoneListAuthProjects({ region })` before querying rules.
   - Do not silently mix a `project_id` from one region with a different `region`.

2. Start with the rule list call.
   - Call `huaweicloud-vpc_ListSecurityGroupRules({ project_id, region, ...filters })`.
   - Prefer narrow filters like `id`, `security_group_id`, `direction`, or `protocol` instead of a wide unfiltered project-wide rule inventory call.
   - If pagination is needed, continue with `marker` and `limit`.

3. Confirm one rule only when needed.
   - If the list result returns one likely target, or the user already provided a `security_group_rule_id`, call `huaweicloud-vpc_ShowSecurityGroupRule({ project_id, region, security_group_rule_id })`.
   - Use this to confirm fields like `security_group_id`, `direction`, `protocol`, `ethertype`, `multiport`, and remote-peer selectors.

4. Interpret remote peers carefully.
   - For `direction=ingress`, `remote_ip_prefix` is the source CIDR or IP.
   - For `direction=egress`, `remote_ip_prefix` is the destination CIDR or IP.
   - `remote_group_id` and `remote_address_group_id` represent different peer selectors and should not be conflated with `remote_ip_prefix`.

## Interpretation rules

- A successful `ListSecurityGroupRules` response with zero matches is not an auth failure by itself; it can simply mean there are no rules in that region/project scope or the filters are too narrow.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still fail or return nothing if the `region` is wrong.
- `ShowSecurityGroupRule` is better for final confirmation than for discovery.
- If the user is only auditing ingress exposure, prefer `direction=ingress` and a specific `security_group_id` to avoid noisy mixed-scope results.

## Safety and scope

- This skill is read-only.
- Do not create, update, or delete security group rules or security groups.
- Do not silently guess a different `project_id`, `region`, `security_group_id`, or `security_group_rule_id`.
- Do not treat the top-level scope `name` hint as an API-safe exact filter unless it has already been normalized.

## Output checklist

1. region used
2. project used
3. filters applied
4. number of rules found
5. key rule fields for each match
6. whether `ShowSecurityGroupRule` was used as follow-up
7. exact blocker if the query failed
8. execution path used: `mcp-tools` or `repo-helper`
