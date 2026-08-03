---
name: huawei-vpc-list-security-group-rules
description: Query Huawei Cloud VPC security group rules through the repo-local standalone helper in scripts/. Use when listing security-group rules, filtering by direction/protocol/ethertype or exact rule IDs, or confirming one rule in detail through scripts/huawei_vpc_security_group_rules.py.
compatibility: Prefers the repo-local standalone VPC helper script and wrapper commands in scripts/. If it is unavailable but Huawei Cloud VPC MCP tools or the repo-local VPC OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: list-security-group-rules
---

# Huawei VPC List Security Group Rules

## What this skill does

- Query security group rules through `scripts/huawei_vpc_security_group_rules.py`.
- Support narrow filters such as `id`, `security_group_id`, `direction`, `protocol`, `ethertype`, `action`, `enabled`, `priority`, and remote-peer selectors.
- Confirm one rule in detail with the `show` action when the target rule is already known.
- Help avoid noisy project-wide enumeration when one security group or one rule ID is already available.
- Return a concise rule summary without mutating any cloud resources.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project VPC scripts.

Primary execution paths:

- `scripts/huawei_vpc_security_group_rules.py`
- `scripts/query-sg-rules.cmd`
- `scripts/show-sg-rule.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

The top-level `name` field in the scope file is an AI-side hint only. Do not pass it directly as a rule API filter unless it has already been normalized to an exact field.

## Runtime fallback when required tools are unavailable

If the repo-local standalone VPC helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud VPC MCP tools or whether the repo-local VPC OpenAPI execution path is available, using:

- `scripts/huawei_vpc_security_group_rules.py`
- `scripts/huawei_scope.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/run.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/vpc.json`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When the standalone helper is present and valid, prefer it. If it is unavailable but the active MCP tool surface or repo-local VPC OpenAPI execution chain can safely perform the same bounded read-only workflow, that path is allowed instead. Only report a blocker when none of those paths can safely provide the required query capability.

## Required inputs

Required directly or through scope defaults:

- `region`
- `project_id`

Optional inputs:

- `id`
- `security_group_id`
- `direction` (`ingress` or `egress`)
- `action` (`allow` or `deny`)
- `protocol`
- `ethertype` (`IPv4` or `IPv6`)
- `enabled`
- `priority`
- `remote_ip_prefix`
- `remote_group_id`
- `remote_address_group_id`
- `description`
- `marker`
- `limit`
- `security_group_rule_id` (for the `show` action only)
- `json_output`

## Default workflow

1. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope <path>`.
   - Apply `region` and `project_id` only when the caller omitted them. Do not silently mix a `project_id` from one region with a different `region`.

2. Choose the action.
   - Inventory / filtered list: action `list`.
   - One known rule in detail: action `show` with `--security-group-rule-id <rule_id>`.

3. Run the primary command.
   - Ingress rules for one security group:
     `python scripts/huawei_vpc_security_group_rules.py list --security-group-id <sg_id> --direction ingress`
   - One rule by ID:
     `python scripts/huawei_vpc_security_group_rules.py show --security-group-rule-id <rule_id> --json-output`
   - By protocol:
     `python scripts/huawei_vpc_security_group_rules.py list --protocol tcp`
   - Prefer narrow filters (`--id`, `--security-group-id`, `--direction`, `--protocol`) over a wide unfiltered project-wide rule inventory call.

4. Summarize the result conservatively.
   - Report the number of rules found.
   - For each returned match, prefer `id`, `direction`, `ethertype`, `protocol`, `multiport`, `action`, and the remote peer selector.

## Interpretation rules

- A successful `list` call with zero results is not an auth failure by itself; it can simply mean there are no rules in that region/project scope or the filters are too narrow.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still return nothing if the `region` is wrong.
- For `direction=ingress`, `remote_ip_prefix` is the source CIDR or IP; for `direction=egress`, it is the destination.
- `remote_group_id` and `remote_address_group_id` are different peer selectors and must not be conflated with `remote_ip_prefix`.
- The `show` action is better for final confirmation than for discovery.
- When auditing ingress exposure, prefer `--direction ingress` plus a specific `--security-group-id` to avoid noisy mixed-scope results.

## Safety and scope

- This skill is read-only.
- Do not create, update, or delete security group rules or security groups.
- Do not silently guess a different `project_id` or `region`.
- Do not print or expose secrets from the scope file.

## Output checklist

1. scope file used
2. region used
3. project used
4. action used (`list` or `show`)
5. filters applied
6. number of rules found
7. key fields for each returned rule
8. whether `--json-output` was used
9. exact blocker if the query failed
10. execution path used: `script`, `mcp-tools`, `repo-helper`, `mixed`, or `not-run`
