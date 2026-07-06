---
name: huawei-cce-list-clusters
description: Query Huawei Cloud CCE clusters with read-only CCE MCP tools. Use when checking cluster inventory, filtering by status/version/type, or confirming one cluster in detail.
compatibility: Prefers Huawei Cloud CCE MCP tools in the current environment. If they are unavailable but the repo-local CCE helper path is present, this skill may use that bounded fallback path instead. IAM MCP tools remain useful follow-ups for project discovery.
metadata:
  domain: huaweicloud
  service: cce
  purpose: list-clusters
---

# Huawei CCE List Clusters

## What this skill does

- Query CCE cluster inventory with read-only operations.
- Support narrow filters like `status`, `type`, `version`, and `detail`.
- Confirm one cluster in detail when the user already knows the exact `cluster_id` or when the list result narrows to one likely target.
- Help avoid the common mistake of mixing the wrong `region` with the wrong `project_id`.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an API filter unless it has already been normalized to an exact cluster name.

Primary tools:

- `huaweicloud-cce_ListClusters`
- `huaweicloud-cce_ShowCluster`

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-iam_KeystoneListProjects`
- `huaweicloud-iam_KeystoneShowProject`

## Runtime fallback when required tools are unavailable

If the expected CCE MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local CCE execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/run.py`
- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/config/config.yaml`
- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/config/cce.json`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/run.py`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/config/cce.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local CCE specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local CCE execution path can safely provide the required capability.

## Required inputs

- `project_id` (or enough region context to discover it with IAM first)

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `detail`
- `status`
- `type`
- `version`
- `cluster_id` (when the user wants one exact cluster detail)

## Default workflow

1. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })`.

2. Confirm the region and project scope first.
   - Use the provided `region` and `project_id` when the user supplied them.
   - If the current MCP runtime already injected defaults from a Huawei scope file, reuse those values and say that they came from configured defaults.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region instead of silently guessing one.
   - If `project_id` is missing, prefer discovering it with `huaweicloud-iam_KeystoneListAuthProjects({ region })` before querying clusters.
   - When discovering `project_id`, prefer the project whose name matches the target `region` exactly; if that still leaves ambiguity, say which project you picked.
   - Do not silently mix a `project_id` from one region with a different `region`.

2. Start with the cluster list call.
   - Call `huaweicloud-cce_ListClusters({ project_id, region, detail?, status?, type?, version? })`.
   - Prefer narrow filters instead of a wide unfiltered inventory call when the user already gave them.
   - Use `detail=true` only when the user needs fuller cluster detail, because it expands the response.

3. Confirm one cluster only after the list is known.
   - If the user already gave an exact `cluster_id`, or the list result clearly narrows to one target, call `huaweicloud-cce_ShowCluster({ project_id, region, cluster_id, detail? })`.
   - Use this to confirm fields like cluster phase, endpoints, and returned metadata.

4. Summarize the result.
   - Report the number of clusters found.
   - For each returned match, prefer to show `id`, `name`, `status.phase` when present, `spec.version`, and `spec.type`.

## Interpretation rules

- A successful `ListClusters` response with zero clusters is not an auth failure by itself; it can simply mean there are no clusters in that region/project scope.
- `project_id` is region-scoped in Huawei Cloud, so an otherwise valid `project_id` can still fail or return nothing if the `region` is wrong.
- `detail=true` is useful for richer inspection, but not required for a lightweight inventory query.
- `type` here is an API filter such as `VirtualMachine` or `ARM64`; do not describe it as a general CCE/Turbo selector unless the target call confirms that meaning.

## Safety and scope

- This skill is read-only.
- Do not create, hibernate, awake, or delete clusters.
- Do not guess a different `project_id`, `region`, or `cluster_id` silently.

## Output checklist

1. region used
2. project used
3. filters applied
4. number of clusters found
5. key cluster fields for each match
6. whether `ShowCluster` was used as follow-up
7. exact blocker if the query failed
8. execution path used: `mcp-tools` or `repo-helper`
