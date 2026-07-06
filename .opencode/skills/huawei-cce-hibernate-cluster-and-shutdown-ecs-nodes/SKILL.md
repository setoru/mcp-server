---
name: huawei-cce-hibernate-cluster-and-shutdown-ecs-nodes
description: Hibernate one known Huawei Cloud CCE cluster and shut down all ECS servers backing its current nodes. Use when the user explicitly wants both actions for one exact cluster.
compatibility: Prefers Huawei Cloud CCE and ECS MCP tools in the current environment. If they are unavailable but the repo-local CCE/ECS helper paths are present, this skill may use those bounded fallback paths instead. IAM MCP tools remain useful follow-ups for project discovery.
metadata:
  domain: huaweicloud
  service: cce
  purpose: hibernate-cluster-and-shutdown-node-ecs
---

# Huawei CCE Hibernate Cluster And Shutdown ECS Nodes

## What this skill does

- Hibernate exactly one known CCE cluster.
- Enumerate the cluster's current nodes and collect the backing ECS server IDs.
- Shut down those ECS servers after the hibernation request is sent.
- Report both mutation steps separately and conservatively.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
Do not use fuzzy cluster names as a substitute for an exact `cluster_id` during a mutating action.
The ECS targets for shutdown must come only from the current `huaweicloud-cce_ListNodes(...)` result for the target cluster.

Primary tools:

- `huaweicloud-cce_ShowCluster`
- `huaweicloud-cce_ListNodes`
- `huaweicloud-cce_HibernateCluster`
- `huaweicloud-ecs_BatchStopServers`

Useful follow-up tools when narrowing scope or confirming results:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-cce_ListClusters`
- `huaweicloud-ecs_ShowServer`

## Runtime fallback when required tools are unavailable

If the expected CCE or ECS MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local CCE/ECS execution paths are available, using one of:

- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/run.py`
- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/config/config.yaml`
- `huaweicloud_services_server/mcp_server_cce/src/mcp_server_cce/config/cce.json`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/run.py`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_cce_lite/src/mcp_server_cce_lite/config/cce.json`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/run.py`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/config/config.yaml`
- `huaweicloud_services_server/mcp_server_ecs/src/mcp_server_ecs/config/ecs.json`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/run.py`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_ecs_lite/src/mcp_server_ecs_lite/config/ecs.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local specs is present and valid for the required operations, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local CCE/ECS execution paths can safely provide the required capabilities.

## Required inputs

- `project_id`
- `cluster_id`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- ECS stop type (default to `SOFT` unless the user explicitly requests `HARD`)

## Default workflow

1. Confirm the user explicitly wants both actions.
   - This skill performs two ordered mutating actions.
   - If the user only asked to hibernate the cluster or only asked to stop ECS servers, use a narrower skill instead.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before mutation.

3. Require the exact target identifiers.
   - If `cluster_id` is missing, ask for it or use `huaweicloud-cce_ListClusters(...)` first as a separate discovery step.
   - Do not pick a cluster by fuzzy name for this action.

4. Perform preflight reads before any mutation.
   - Call `huaweicloud-cce_ShowCluster({ project_id, region, cluster_id })` first.
   - If the cluster is already hibernated, hibernating, unavailable, deleting, or otherwise clearly unsuitable for a new hibernate request, stop and report the blocker instead of forcing the mutation.
   - Call `huaweicloud-cce_ListNodes({ project_id, region, cluster_id })` and collect every non-empty `status.serverId`.
   - Nodes without a non-empty `status.serverId` must be skipped and reported; do not resolve ECS targets by node name, tags, or a separate ECS search.
   - Deduplicate the ECS server IDs before shutdown.

5. Hibernate the cluster once.
   - Call `huaweicloud-cce_HibernateCluster({ project_id, region, cluster_id })`.
   - Treat an empty success body as request acceptance, not as proof that the cluster already reached `Hibernation`.

6. Shut down the current node ECS servers.
   - Continue to ECS shutdown only after the hibernate request was accepted.
   - If the node list returned zero ECS server IDs, stop after the hibernate step and report that there were no backing ECS targets to shut down.
   - Otherwise call `huaweicloud-ecs_BatchStopServers({ project_id, region, servers, type })` using the deduplicated server ID list.
   - Default the stop type to `SOFT` unless the user explicitly requested `HARD`.

7. Re-read and report results conservatively.
   - Attempt one follow-up `huaweicloud-cce_ShowCluster(...)` read after the mutations.
   - Attempt at least one follow-up `huaweicloud-ecs_ShowServer(...)` read for a submitted ECS target after the mutations.
   - If a follow-up read is not performed, say explicitly that confirmation was skipped.
   - Report hibernation status and ECS power status separately.
   - Do not claim terminal completion unless the follow-up reads confirm it.

## Interpretation rules

- A successful node list with zero items is valid and means there were no current node ECS servers to stop.
- A node without `status.serverId` is not a valid ECS shutdown target and must be reported as skipped.
- A successful hibernate response means the request was accepted; it does not by itself prove the cluster is already in `Hibernation`.
- A successful ECS batch stop response may return only a job identifier; use follow-up reads to confirm `SHUTOFF` when confirmation is required.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.

## Safety and scope

- This skill performs two ordered mutating actions.
- Do not fuzzy-match the target cluster.
- Do not guess ECS targets outside the returned node list.
- Do not use `HARD` stop unless the user explicitly requests it.
- Do not chain wake, retry, delete, or cleanup mutations.
- If the hibernate step fails, stop and do not attempt ECS shutdown.
- If the hibernate step succeeds but ECS shutdown is skipped or fails, report a partial outcome clearly.
- Do not claim the cluster is fully hibernated or the ECS servers are fully stopped unless later reads confirm the terminal states.

## Output checklist

1. region used
2. project used
3. exact cluster targeted
4. preflight cluster phase or blocker
5. number of nodes found
6. number of unique ECS server IDs selected
7. nodes skipped because no `serverId`, if any
8. exact ECS server IDs submitted for shutdown
9. stop type used: `SOFT` or `HARD`
10. whether the hibernate request was accepted
11. whether the ECS stop request was accepted
12. async job identifier if the ECS stop API returned one
13. confirmed cluster phase after follow-up, if checked
14. confirmed ECS power status after follow-up, if checked
15. overall outcome: `completed`, `partially completed`, or `blocked`
16. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
