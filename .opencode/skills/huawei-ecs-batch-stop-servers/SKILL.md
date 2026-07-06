---
name: huawei-ecs-batch-stop-servers
description: Batch stop Huawei Cloud ECS servers by explicit ID list. Use when the user explicitly wants one or more ECS instances shut down and the stop type is known or can default to soft stop.
compatibility: Prefers Huawei Cloud IAM and ECS MCP tools in the current environment. If ECS tools are unavailable but the repo-local ECS helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: ecs
  purpose: batch-stop-servers
---

# Huawei ECS Batch Stop Servers

## What this skill does

- Batch stop ECS servers by explicit ID list.
- Default to soft stop unless the user explicitly requests hard stop.
- Report acceptance and follow-up status conservatively.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.

Primary tools:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-ecs_BatchStopServers`

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
- `type` (`SOFT` by default, `HARD` only when explicitly requested)

## Default workflow

1. Confirm explicit stop intent.
   - This skill performs a mutating stop action.
   - Use it only when the user has already explicitly asked to stop the target ECS servers.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before stopping servers.

3. Require exact stop targets.
   - Require one or more exact ECS server IDs.
   - Deduplicate the ID list before submission.
   - Do not fuzzy-match servers by name.

4. Perform a minimal preflight lookup before stopping.
   - Confirm one or more target ECS IDs in the requested region/project scope with a minimal ECS read path when practical.
   - If the requested IDs cannot be confirmed in this scope, stop and report that blocker instead of stopping blindly.

5. Submit the stop request once.
   - `huaweicloud-ecs_BatchStopServers({ project_id, region, servers, type? })`
   - Default `type` to `SOFT` unless the user explicitly requested `HARD`.
   - Treat the response as request acceptance, not as proof that every server is already `SHUTOFF`.

6. Optionally re-check follow-up status.
   - When practical, confirm one or more targeted servers with `huaweicloud-ecs_ShowServer({ project_id, region, server_id })`.
   - If no follow-up read is performed, say explicitly that confirmation was skipped.

## Interpretation rules

- ECS batch stop is asynchronous; a successful response means the request was accepted, not that all servers have already reached `SHUTOFF`.
- `SOFT` is the default graceful stop type; `HARD` is forceful and should be used only on explicit user request.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- `completed`, `partially completed`, and `blocked` in this skill are request-stage outcomes, not proof that all targeted ECS servers are already fully stopped.

## Safety and scope

- This skill performs one mutating stop action.
- Stop only the explicitly identified ECS server IDs.
- Do not infer or fuzzy-match targets.
- Do not chain delete or reboot operations.
- Do not use `HARD` stop unless the user explicitly requested it.

## Output checklist

1. region used
2. project used
3. exact ECS server IDs targeted
4. preflight result
5. stop type used: `SOFT` or `HARD`
6. whether the stop request was accepted
7. confirmed server power status after follow-up, if checked
8. whether follow-up confirmation was skipped and why
9. exact blocker if stop was incomplete
10. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
11. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
