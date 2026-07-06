---
name: huawei-nat-list-gateways
description: List Huawei Cloud public NAT gateways through the repo-local NAT MCP server. Use when checking NAT gateway inventory, filtering by ID or name, or validating project and region scope.
compatibility: Prefers the repo's opencode.json to expose the local `huaweicloud-nat` MCP server. If that tool is unavailable but the repo-local NAT helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: nat
  purpose: list-gateways
---

# Huawei NAT List Gateways

## What this skill does

- Query public NAT gateway instances.
- Support narrow filters like `id`, `name`, `router_id`, `status`, and `spec`.
- Return a concise inventory summary without mutating any cloud resources.

## Tool assumptions

This skill expects the project-local MCP server name to be `huaweicloud-nat`, so the primary tool is:

- `huaweicloud-nat_ListNatGateways`

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an API filter unless it has already been normalized to an exact gateway name.

## Runtime fallback when required tools are unavailable

If the expected NAT MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local NAT execution path is available, using:

- `huaweicloud_services_server/mcp_server_nat/src/mcp_server_nat/run.py`
- `huaweicloud_services_server/mcp_server_nat/src/mcp_server_nat/config/config.yaml`
- `huaweicloud_services_server/mcp_server_nat/src/mcp_server_nat/config/nat.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When that repo-local NAT spec is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local NAT execution path can safely provide the required capability.

## Required inputs

- `project_id`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `id`
- `name`
- `router_id`
- `status`
- `spec`
- `limit`
- `enterprise_project_id`

## Default workflow

1. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.

2. Resolve project scope.
   - Use the provided or scope-extracted `project_id`.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` and prefer the project whose name matches the current `region`.
   - If `project_id` is still ambiguous after discovery, state which project you picked.

3. Call the read-only NAT tool:
   - `huaweicloud-nat_ListNatGateways({ project_id, region, ...filters })`

4. Summarize the result.
   - Report the number of gateways found.
   - For each gateway returned, prefer to show: `id`, `name`, `status`, `router_id`, `spec`.

## Safety and scope

- This skill is read-only.
- Do not create, update, or delete anything.
- Do not infer a different `project_id` or `region` silently.

## Output checklist

1. region used
2. project used
3. filters applied
4. number of gateways found
5. key gateway fields for each match
6. execution path used: `mcp-tools` or `repo-helper`
