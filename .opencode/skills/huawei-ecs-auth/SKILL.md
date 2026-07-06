---
name: huawei-ecs-auth
description: Query Huawei Cloud ECS resources and validate whether the current mcp-server credentials, region, and project access are usable. Use when checking Huawei Cloud authentication, listing ECS servers, confirming project_id, or diagnosing ECS read permission failures.
compatibility: Prefers Huawei Cloud IAM and ECS MCP tools in the current environment. If ECS tools are unavailable but the repo-local ECS helper path is present, this skill may use that bounded fallback path plus the shared IAM project-discovery flow instead.
metadata:
  domain: huaweicloud
  service: ecs
  purpose: credential-validation
---

# Huawei Cloud ECS Auth

## What this skill does

- Validate whether the current Huawei Cloud credentials configured for MCP are usable.
- Discover or confirm a usable `project_id` before querying ECS.
- Query ECS servers with read-only operations.
- Distinguish between missing credentials, invalid credentials, wrong region/project, missing permissions, and a valid but empty ECS result.

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

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneShowProject`

## Runtime fallback when required tools are unavailable

If the expected IAM or ECS MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local ECS execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/run.py`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/config/config.yaml`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/config/ecs.json`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/run.py`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/config/ecs.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local ECS specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain plus the shared IAM project-discovery flow to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local ECS execution path can safely provide the required capability.

## Default workflow

1. **Check whether credentials are present indirectly through tool behavior.**
   - Do not ask the user for AK/SK first.
   - Start with read-only Huawei Cloud MCP calls.
   - If the tool returns a missing-credentials style failure, explain that this repo expects `HUAWEI_ACCESS_KEY` and `HUAWEI_SECRET_KEY` (or equivalent `ak`/`sk` config in the server config), then stop.

2. **Read `.opencode/huawei-scope.yaml` first.**
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.

3. **Discover project access.**
   - Call `huaweicloud-iam_KeystoneListAuthProjects({ region })` with the resolved region.
   - If there are no returned projects, do not claim auth success. Explain that the credentials may be invalid, the region may be wrong, or the account may not have visible projects there.

4. **Choose the project to test.**
   - If there is exactly one accessible project, use it.
   - If there is a project whose name equals the requested `region`, prefer that project first.
   - If there are multiple projects and the user did not specify one, prefer the first returned project for a lightweight credential test, but explicitly state that assumption.
   - If the user asked for a specific project, use that exact `project_id`.

5. **Run the primary ECS validation call.**
   - Prefer:
     - `huaweicloud-ecs_ListServersDetails({ project_id, region, limit: 10 })`
   - Acceptable fallback:
     - `huaweicloud-ecs_ListCloudServers({ project_id, region, limit: 10 })`
   - Treat a successful response with an empty server list as **valid credentials and readable ECS scope, but no ECS instances found**.

5. **Optionally confirm single-instance read access.**
   - If the list response includes at least one server ID, call:
     - `huaweicloud-ecs_ShowServer({ project_id, region, server_id })`
   - Use this as a stronger confirmation that ECS read access is working end-to-end.

6. **Report result using the correct category.**
   - `valid credentials + ECS access confirmed`
   - `valid credentials + no ECS instances in this scope`
   - `credentials missing`
   - `credentials invalid or signature/auth failed`
   - `project_id or region mismatch`
   - `permission denied for ECS read`

## Interpretation rules

- A successful IAM project listing plus a successful ECS list call means the current MCP-server credentials are usable for ECS read operations in that region/project scope.
- A successful ECS list call with zero resources is **not** an auth failure.
- Do not confuse “no ECS in this region/project” with “credentials invalid”.
- Do not ask the user to pass `X-Auth-Token`; this repo already uses AK/SK-based signing in the shared Huawei client flow.
- Do not perform mutating ECS operations when the task is only credential verification.

## Safety and scope

- Only use read-only IAM/ECS operations unless the user explicitly asks for a mutating action.
- Prefer the smallest query that proves access.
- If the request is only “verify credentials”, stop after IAM + ECS read verification. Do not enumerate extra resources unnecessarily.

## Output checklist

When using this skill, report:

1. region used
2. project used
3. which tool call proved access
4. whether ECS resources were found
5. exact blocker if verification failed
6. execution path used: `mcp-tools` or `repo-helper`

## References

- See `references/auth-failures.md`
- See `references/region-project-checklist.md`
