---
name: huawei-elb-delete-loadbalancer
description: Delete one known Huawei Cloud ELB load balancer by exact ID through the repo-local standalone ELB helper in this project. Use when the user explicitly wants that exact ELB instance removed and the project-standard delete behavior should default to cascade cleanup through scripts/huawei_elb_loadbalancer.py.
compatibility: Prefers the repo-local standalone ELB helper script and wrapper commands in scripts/. If they are unavailable but Huawei Cloud ELB MCP tools or the repo-local ELB OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: elb
  purpose: delete-loadbalancer
---

# Huawei ELB Delete Load Balancer

## What this skill does

- Delete exactly one ELB load balancer by explicit ID through `scripts/huawei_elb_loadbalancer.py`.
- Default to cascade delete.
- Still support standard delete when explicitly requested.
- Support preserving the associated public IP or unbounded pool during cascade delete when explicitly requested.
- Stop after the delete request returns and report the immediate result conservatively.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project ELB scripts.

Primary execution paths:

- `scripts/huawei_elb_loadbalancer.py`
- `scripts/delete-elb.cmd`
- `scripts/query-elb.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope-file` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

This skill must target exactly one explicit ELB load balancer ID. Do not infer or fuzzy-match a load balancer from name alone during a destructive action.

## Runtime fallback when required tools are unavailable

If the repo-local standalone ELB helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud ELB MCP tools or whether the repo-local ELB OpenAPI execution path is available, using:

- `scripts/huawei_elb_loadbalancer.py`
- `scripts/delete-elb.cmd`
- `scripts/query-elb.cmd`
- `scripts/huawei_scope.py`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/run.py`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/config/config.yaml`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/config/elb.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When the standalone helper is present and valid, prefer it. If it is unavailable but the active MCP tool surface or repo-local ELB OpenAPI execution chain can safely perform the same bounded delete workflow, that path is allowed instead. Only report a blocker when none of those paths can safely provide the required delete capability.

## Required inputs

Required directly or through scope defaults:

- `region`
- `project_id`
- `loadbalancer_id`

Optional inputs:

- `no_cascade`
- `keep_public_ip`
- `keep_unbounded_pool`

## Default workflow

1. Confirm explicit delete intent.
   - This skill is destructive.
   - Use it only when the user has already explicitly asked to delete one exact ELB load balancer.

2. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope-file <path>`.

3. Require an explicit `loadbalancer_id`.
   - Do not infer or fuzzy-match a target load balancer.

4. Run a minimal preflight lookup when practical.
   - Prefer:
     `python scripts/huawei_elb_loadbalancer.py list --id <loadbalancer_id> --json-output`
   - If the target is not found in this scope, stop and report that blocker.

5. Delete the explicit load balancer once.
   - Cascade delete:
     `python scripts/huawei_elb_loadbalancer.py delete --loadbalancer-id <loadbalancer_id>`
   - Explicit cascade delete:
     `python scripts/huawei_elb_loadbalancer.py delete --loadbalancer-id <loadbalancer_id> --cascade`
   - Standard delete only when explicitly requested:
     `python scripts/huawei_elb_loadbalancer.py delete --loadbalancer-id <loadbalancer_id> --no-cascade`
   - Preserve associated public IP during cascade delete only when the user explicitly asked:
     `python scripts/huawei_elb_loadbalancer.py delete --loadbalancer-id <loadbalancer_id> --keep-public-ip`
   - Preserve associated unbounded pool during cascade delete only when the user explicitly asked:
     `python scripts/huawei_elb_loadbalancer.py delete --loadbalancer-id <loadbalancer_id> --keep-unbounded-pool`

6. Stop after the delete result.
   - Treat the returned response as request acceptance, not as proof that the ELB has already fully disappeared.

## Interpretation rules

- ELB deletion is asynchronous; a successful delete response means the request was accepted, not that the ELB is already gone.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a project from one region with another region.
- Cascade delete is the project-standard default for this helper and can also remove associated resources.
- Use `--no-cascade` only when the user explicitly wants to preserve dependent resources through the standard delete API.

## Safety and scope

- This skill is destructive.
- Delete only the explicitly identified load balancer ID.
- Do not infer or fuzzy-match delete targets.
- Treat cascade delete as the default path.
- Use `--no-cascade` only when the user explicitly asked for standard delete semantics.
- Use `--keep-public-ip` or `--keep-unbounded-pool` only when the user explicitly asked to preserve those dependencies.
- Do not print or expose secrets from the scope file.

## Output checklist

1. scope file used
2. region used
3. project used
4. exact ELB load balancer ID targeted
5. whether preflight lookup was used and what it found
6. whether default cascade delete or explicit standard delete was requested
7. whether the delete request was accepted
8. exact blocker if deletion failed or was incomplete
9. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
10. execution path used: `script`, `mcp-tools`, `repo-helper`, `mixed`, or `not-run`
