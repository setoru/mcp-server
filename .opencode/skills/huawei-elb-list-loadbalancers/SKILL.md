---
name: huawei-elb-list-loadbalancers
description: Query Huawei Cloud ELB load balancers through the repo-local standalone ELB helper in this project. Use when listing ELB inventory, filtering by ID or name, checking provisioning state, or confirming ELBs created by scripts/huawei_elb_loadbalancer.py.
compatibility: Prefers the repo-local standalone ELB helper script and wrapper commands in scripts/. If they are unavailable but Huawei Cloud ELB MCP tools or the repo-local ELB OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: elb
  purpose: list-loadbalancers
---

# Huawei ELB List Load Balancers

## What this skill does

- Query ELB load balancer instances through `scripts/huawei_elb_loadbalancer.py`.
- Support exact or narrow filters such as `id`, `name`, `provisioning_status`, `operating_status`, `vip_address`, `vip_subnet_id`, and `vpc_id`.
- Optionally print full JSON output when exact response details matter.
- Return a concise inventory summary without mutating any cloud resources.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project ELB scripts.

Primary execution paths:

- `scripts/huawei_elb_loadbalancer.py`
- `scripts/query-elb.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope-file` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

The top-level `name` field in the scope file is an AI-side hint only. Do not pass it directly as an ELB list filter unless it has already been normalized to an exact load balancer name.

## Runtime fallback when required tools are unavailable

If the repo-local standalone ELB helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud ELB MCP tools or whether the repo-local ELB OpenAPI execution path is available, using:

- `scripts/huawei_elb_loadbalancer.py`
- `scripts/query-elb.cmd`
- `scripts/huawei_scope.py`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/run.py`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/config/config.yaml`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/config/elb.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When the standalone helper is present and valid, prefer it. If it is unavailable but the active MCP tool surface or repo-local ELB OpenAPI execution chain can safely perform the same bounded read-only workflow, that path is allowed instead. Only report a blocker when none of those paths can safely provide the required query capability.

## Required inputs

Required directly or through scope defaults:

- `region`
- `project_id`

Optional inputs:

- `id`
- `name`
- `provisioning_status`
- `operating_status`
- `vip_address`
- `vip_subnet_id`
- `vpc_id`
- `admin_state_up`
- `enterprise_project_id`
- `marker`
- `limit`
- `json_output`

## Default workflow

1. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope-file <path>`.

2. Run the primary ELB list command.
   - General inventory:
     `python scripts/huawei_elb_loadbalancer.py list`
   - Exact ID lookup:
     `python scripts/huawei_elb_loadbalancer.py list --id <loadbalancer_id> --json-output`
   - Name filter:
     `python scripts/huawei_elb_loadbalancer.py list --name <exact_name>`

3. Use JSON output when precision matters.
   - Prefer `--json-output` when the user wants raw response details or when a follow-up delete target must be confirmed exactly.

4. Summarize the result conservatively.
   - Report the number of load balancers found.
   - For each returned match, prefer `id`, `name`, `provisioning_status`, `operating_status`, `vip_address`, and `vip_subnet_id`.

## Interpretation rules

- A successful list call with zero results is not an auth failure by itself; it can simply mean there are no ELBs in that region and project scope.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still return nothing if `region` is wrong.
- The helper uses exact `--name` filtering, so do not treat fuzzy name matches as confirmed targets.

## Safety and scope

- This skill is read-only.
- Do not create, update, or delete anything.
- Do not infer a different `project_id` or `region` silently.
- Do not print or expose secrets from the scope file.

## Output checklist

1. scope file used
2. region used
3. project used
4. filters applied
5. number of load balancers found
6. key fields for each returned load balancer
7. whether `--json-output` was used
8. exact blocker if the query failed
9. execution path used: `script`, `mcp-tools`, `repo-helper`, `mixed`, or `not-run`
