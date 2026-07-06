---
name: huawei-ecs-delete-servers
description: Delete Huawei Cloud ECS servers by explicit ID list. Use when the user explicitly wants specific ECS instances removed; by default the repo script deletes attached public IPs and data volumes unless the user explicitly asks to keep them.
compatibility: Prefers Huawei Cloud IAM and ECS MCP tools in the current environment. If ECS tools are unavailable but the repo-local ECS helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: ecs
  purpose: delete-servers
---

# Huawei ECS Delete Servers

## What this skill does

- Delete ECS servers by explicit ID list.
- Perform a minimal preflight read before deletion when practical.
- Stop after the delete call returns and report the immediate result conservatively.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.

Primary tools:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-ecs_ListServersDetails`
- `huaweicloud-ecs_DeleteServers`

Useful follow-up tools:

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

- `project_id`
- one or more explicit ECS server IDs

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `delete_publicip`
- `delete_volume`

## Default workflow

1. Confirm explicit delete intent.
   - This skill is destructive.
   - Use it only when the user has already explicitly asked to delete the target ECS servers.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before deletion.

3. Require explicit delete inputs.
   - Require one or more exact ECS server IDs.
   - Do not fuzzy-match servers by name.
   - If the ID list exceeds the API batch limit, stop and report that blocker instead of truncating silently.
   - If `delete_publicip` or `delete_volume` is not provided, follow the repo script default: attached EIPs and data volumes are deleted.
   - Preserve attached resources only when the user explicitly asks for `delete_publicip=false` or `delete_volume=false`.

4. Perform a minimal preflight lookup.
   - Query the target IDs with a minimal ECS read path that can verify each explicit server ID in the requested scope.
   - Report how many requested IDs were confirmed by preflight.
   - If any requested IDs are not found in this scope, stop and report that blocker.

5. Delete the explicit server ID list once.
   - `huaweicloud-ecs_DeleteServers({ project_id, region, servers, delete_publicip?, delete_volume? })`
   - Treat the returned response as request acceptance, not as proof that the servers are already gone.

## Interpretation rules

- ECS deletion is asynchronous; a successful delete response means the request was accepted, not that the servers have fully disappeared.
- `delete_publicip=true` and `delete_volume=true` are the repo script defaults.
- `delete_publicip=false` and `delete_volume=false` keep attached EIPs and data volumes instead of deleting them.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- `completed`, `partially completed`, and `blocked` in this skill are request-stage outcomes, not proof that the ECS servers are already fully gone.

## Safety and scope

- This skill is destructive.
- Delete only the explicitly identified ECS server IDs.
- Do not infer or fuzzy-match delete targets.
- By default, delete attached public IPs and data volumes with the ECS delete request.
- Keep attached public IPs or data volumes only when that preservation behavior is explicit.
- Do not chain follow-up cleanup mutations.

## Output checklist

1. region used
2. project used
3. exact ECS server IDs targeted
4. preflight result, including how many requested IDs were confirmed
5. delete flags used for public IPs and volumes
6. whether the delete request was accepted
7. whether follow-up deletion verification was skipped and why
8. exact blocker if deletion failed or was incomplete
9. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
10. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
