---
name: huawei-vpc-list-security-groups
description: Query Huawei Cloud VPC security groups through the repo-local standalone helper in scripts/. Use when listing security-group inventory, filtering by exact IDs or names, or confirming one security group in detail through scripts/huawei_vpc_security_groups.py.
compatibility: Prefers the repo-local standalone VPC helper script and wrapper commands in scripts/. If it is unavailable but Huawei Cloud VPC MCP tools or the repo-local VPC OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: list-security-groups
---

# Huawei VPC List Security Groups

## What this skill does

- Query security-group inventory through `scripts/huawei_vpc_security_groups.py`.
- Support narrow filters such as `id`, `name`, `description`, and `enterprise_project_id`.
- Confirm one security group in detail with the `show` action when the target is already known.
- Help avoid mixing the wrong `region` with the wrong `project_id`.
- Return a concise inventory summary without mutating any cloud resources.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project VPC scripts.

Primary execution paths:

- `scripts/huawei_vpc_security_groups.py`
- `scripts/query-sg.cmd`
- `scripts/show-sg.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

The top-level `name` field in the scope file is an AI-side hint only. Do not pass it directly as a security-group API filter unless it has already been normalized to an exact resource name.

## Runtime fallback when required tools are unavailable

If the repo-local standalone VPC helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud VPC MCP tools or whether the repo-local VPC OpenAPI execution path is available, using:

- `scripts/huawei_vpc_security_groups.py`
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
- `name`
- `description`
- `enterprise_project_id`
- `marker`
- `limit`
- `security_group_id` (for the `show` action only)
- `json_output`

## Default workflow

1. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope <path>`.
   - Apply `region` and `project_id` only when the caller omitted them. Do not silently mix a `project_id` from one region with a different `region`.

2. Choose the action.
   - Inventory / filtered list: action `list`.
   - One known security group in detail: action `show` with `--security-group-id <group_id>`.

3. Run the primary command.
   - General inventory:
     `python scripts/huawei_vpc_security_groups.py list`
   - Exact ID lookup:
     `python scripts/huawei_vpc_security_groups.py list --id <security_group_id>`
   - Exact name filter:
     `python scripts/huawei_vpc_security_groups.py list --name <exact_name> --json-output`
   - One detail lookup:
     `python scripts/huawei_vpc_security_groups.py show --security-group-id <security_group_id> --json-output`
   - Prefer narrow filters (`--id`, `--name`, `--enterprise-project-id`) over a wide unfiltered inventory call.

4. Summarize the result conservatively.
   - Report the number of security groups found.
   - For each returned match, prefer `id`, `name`, `vpc_id`, and `description`.
   - Use `--json-output` when the caller needs raw response details.

## Interpretation rules

- A successful `list` call with zero results is not an auth failure by itself; it can simply mean there are no security groups in that region/project scope or the filters are too narrow.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still return nothing if the `region` is wrong.
- The helper uses exact `--name` filtering, so do not treat fuzzy name matches as confirmed targets.
- The `show` action is better for final confirmation than for discovery.

## Safety and scope

- This skill is read-only.
- Do not create, update, or delete security groups or security group rules.
- Do not silently guess a different `project_id` or `region`.
- Do not print or expose secrets from the scope file.

## Output checklist

1. scope file used
2. region used
3. project used
4. action used (`list` or `show`)
5. filters applied
6. number of security groups found
7. key fields for each returned group
8. whether `--json-output` was used
9. exact blocker if the query failed
10. execution path used: `script`, `mcp-tools`, `repo-helper`, `mixed`, or `not-run`
