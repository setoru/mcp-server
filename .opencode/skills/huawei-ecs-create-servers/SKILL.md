---
name: huawei-ecs-create-servers
description: Create one or more Huawei Cloud ECS servers with explicit inputs. Use when the user intentionally wants new ECS instances and already knows the core image, flavor, network, disk, and login settings.
compatibility: Prefers Huawei Cloud IAM and ECS MCP tools in the current environment. If ECS tools are unavailable but the repo-local ECS helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: ecs
  purpose: create-servers
---

# Huawei ECS Create Servers

## What this skill does

- Create one or more ECS servers.
- Stop after the create call returns.
- Report the returned job or reservation information conservatively.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.

Primary tools:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-ecs_CreateServers`

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
- `server.name`
- `server.imageRef`
- `server.flavorRef`
- `server.vpcid`
- `server.nics`
- `server.root_volume`
- exactly one login mode: `server.key_name` or `server.adminPass`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `server.count`
- `server.description`
- `server.security_groups`
- `server.publicip`
- `server.data_volumes`
- `server.extendparam.enterprise_project_id`
- `dry_run`

## Default workflow

1. Confirm explicit create intent.
   - This skill performs a mutating create action.
   - Use it only when the user already explicitly wants new ECS servers created.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before creation.

3. Require explicit create inputs.
   - If any required creation field is missing, stop and ask for that exact field.
   - Require exactly one login mode: key pair or password.
   - Treat `server.count` as `1` unless the user explicitly requests a larger number.
   - If `server.count` is greater than `1`, confirm that the user explicitly asked for batch creation and report that count clearly.
   - Do not guess image IDs, flavor IDs, VPC IDs, subnet IDs, disk types, or security groups.

4. Call the create tool once.
   - `huaweicloud-ecs_CreateServers({ project_id, region, server, dry_run? })`
   - Treat a returned reservation ID or job-style acceptance as request acceptance, not as proof that the servers are already `ACTIVE`.

5. Stop after the create result.
   - Report the returned identifiers and pending state conservatively.

## Interpretation rules

- ECS creation is asynchronous; a successful create response means the request was accepted, not that server provisioning has fully completed.
- `dry_run=true` is a preflight check only and must not be reported as actual server creation.
- Key-pair login is generally safer than password login; if both are missing, that is a blocker.
- `completed`, `partially completed`, and `blocked` in this skill are request-stage outcomes, not proof that the created ECS servers are already fully provisioned.

## Safety and scope

- This skill performs one mutating create action.
- Do not auto-create follow-up resources beyond what the explicit ECS create payload requests.
- Do not chain stop, reboot, or delete actions after creation.
- Do not guess billable settings or login credentials.

## Output checklist

1. region used
2. project used
3. create payload fields actually sent, with secrets such as `server.adminPass` or equivalent sensitive data redacted
4. whether `dry_run` was used
5. returned job/reservation identifiers
6. number of requested servers
7. exact blocker if creation was incomplete or refused
8. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
9. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
