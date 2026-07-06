---
name: huawei-ecs-list-servers
description: Query Huawei Cloud ECS servers in a resolved region/project scope. Use when listing ECS instances, filtering by state or name, or confirming one server in detail.
compatibility: Prefers Huawei Cloud IAM and ECS MCP tools in the current environment. If ECS tools are unavailable but the repo-local ECS helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: ecs
  purpose: list-servers
---

# Huawei ECS List Servers

## What this skill does

- Query ECS servers with detailed information.
- Support narrow filters such as `name`, `status`, `server_id`, `ip`, and `enterprise_project_id`.
- Optionally confirm one exact ECS server in detail when the list result narrows to one target.
- Return a concise inventory summary without mutating any cloud resources.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an ECS API filter unless it has already been normalized to an exact resource name.

Primary tools:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-ecs_ListServersDetails`
- `huaweicloud-ecs_ListCloudServers`
- `huaweicloud-ecs_ShowServer`

## Runtime fallback when required tools are unavailable

If the expected ECS MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local ECS execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/run.py`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/config/config.yaml`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/config/ecs.json`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/run.py`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/config/ecs.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local ECS specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local ECS execution path can safely provide the required capability.

## Required inputs

- `project_id` or enough scope to discover it

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `name`
- `status`
- `server_id`
- `ip`
- `enterprise_project_id`
- `limit`

## Default workflow

1. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` and prefer the project whose name matches the current `region`.

2. Run the primary ECS list call.
   - Prefer `huaweicloud-ecs_ListServersDetails({ project_id, region, ...filters })`.
   - Use `huaweicloud-ecs_ListCloudServers(...)` only as a fallback when the detailed list call is unavailable or unsuitable for the requested fields.

3. Optionally confirm one server in detail.
   - If the user already supplied an exact `server_id`, or the list clearly narrows to one target, call `huaweicloud-ecs_ShowServer({ project_id, region, server_id })`.
   - Use this to confirm status and detailed instance information conservatively.

4. Summarize the result.
   - Report the number of servers found.
   - For each returned match, prefer to show `id`, `name`, `status`, key IP information, and flavor when present.

## Interpretation rules

- A successful ECS list call with zero results is not an auth failure by itself; it can simply mean there are no ECS instances in that region/project scope.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still fail or return nothing if the `region` is wrong.
- `ListServersDetails` is the preferred detailed inventory call; `ListCloudServers` is a lighter list alternative.

## Safety and scope

- This skill is read-only.
- Do not create, stop, reboot, or delete anything.
- Do not infer a different `project_id` or `region` silently.

## Output checklist

1. region used
2. project used
3. filters applied
4. number of servers found
5. key fields for each returned server
6. whether `ShowServer` was used as follow-up
7. exact blocker if the query failed
8. execution path used: `mcp-tools` or `repo-helper`
