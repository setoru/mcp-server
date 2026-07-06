---
name: huawei-cce-awake-cluster
description: Wake a Huawei Cloud CCE cluster through the built-in CCE MCP tools. Use when the user explicitly wants to wake one known cluster by ID.
compatibility: Prefers Huawei Cloud CCE MCP tools in the current environment. If they are unavailable but the repo-local CCE helper path is present, this skill may use that bounded fallback path instead. IAM MCP tools remain useful follow-ups for project discovery.
metadata:
  domain: huaweicloud
  service: cce
  purpose: awake-cluster
---

# Huawei CCE Awake Cluster

## What this skill does

- Wake exactly one known CCE cluster.
- Perform a minimal preflight check before the awake call.
- Stop after the awake request returns and report the immediate result.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
Do not use fuzzy cluster names as a substitute for an exact `cluster_id` during a mutating action.

Primary tools:

- `huaweicloud-cce_ShowCluster`
- `huaweicloud-cce_AwakeCluster`

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-cce_ListClusters`

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

- `project_id`
- `cluster_id`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)

## Default workflow

1. Confirm the user explicitly wants to wake a cluster.
   - This is a state-changing action.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before wake-up.

3. Require the exact target identifiers.
   - If `cluster_id` is missing, ask for it or use `huaweicloud-cce_ListClusters(...)` first as a separate discovery step.
   - Do not pick a cluster by fuzzy name for this action.

4. Perform a minimal preflight lookup.
   - Call `huaweicloud-cce_ShowCluster({ project_id, region, cluster_id })` first.
   - If the cluster is already available, awaking, unavailable, or otherwise not a sensible target, stop and report the blocker instead of forcing the mutation.

5. Call the awake tool once.
   - `huaweicloud-cce_AwakeCluster({ project_id, region, cluster_id })`

6. Stop after the result.
   - Report that the request was accepted, and note that the cluster still needs to transition to `Available` before the operation is complete.

## Safety and scope

- This skill performs one mutating action.
- Do not fuzzy-match the target cluster.
- Do not chain hibernate, retry, or cleanup mutations.
- Do not claim the cluster is fully awake unless a later read confirms the terminal state.

## Output checklist

1. region used
2. project used
3. exact cluster targeted
4. preflight phase or blocker
5. whether the awake request was accepted
6. reminder that final success is reached only after the cluster state becomes `Available`
7. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
