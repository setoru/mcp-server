---
name: huawei-nat-delete-gateway-with-snat-cleanup
description: Delete one known Huawei Cloud public NAT gateway by explicit ID, removing only the blocking SNAT rules attached to that same gateway when necessary. Use when the user explicitly wants this exact gateway deleted and does not need an extra confirmation prompt inside the skill.
compatibility: Prefers the repo's opencode.json to expose the local `huaweicloud-nat` MCP server. If that tool is unavailable but the repo-local NAT helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: nat
  purpose: delete-gateway-with-snat-cleanup
---

# Huawei NAT Delete Gateway With SNAT Cleanup

## What this skill does

- Delete exactly one public NAT gateway by explicit ID.
- Perform a minimal preflight lookup before deletion.
- If gateway deletion is blocked by SNAT-rule dependencies, enumerate and delete only the blocking SNAT rules attached to that same gateway.
- Retry the gateway deletion once after SNAT cleanup and report the final outcome conservatively.

## Tool assumptions

This skill expects the project-local MCP server name to be `huaweicloud-nat`, so the primary tools are:

- `huaweicloud-nat_ListNatGateways`
- `huaweicloud-nat_DeleteNatGateway`
- `huaweicloud-nat_ListNatGatewaySnatRules`
- `huaweicloud-nat_DeleteNatGatewaySnatRule`

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
This skill must target exactly one explicit NAT gateway ID. Do not infer or fuzzy-match a gateway from name alone during a destructive action.

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
- `nat_gateway_id`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)

## Default workflow

1. Confirm explicit user intent and exact target scope.
   - This skill is destructive.
   - Use it only when the user has already explicitly asked to delete one exact NAT gateway.
   - Once explicit user intent and exact target ID are established, do not add an extra confirmation prompt inside this skill.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before deletion.

3. Require an explicit `nat_gateway_id`.
   - Do not infer or fuzzy-match a target gateway.

4. Run a minimal preflight lookup.
   - Call `huaweicloud-nat_ListNatGateways({ project_id, region, id: nat_gateway_id })` first.
   - If no gateway is returned, stop and report that the target was not found in this scope.

5. Attempt to delete exactly that gateway once.
   - Call `huaweicloud-nat_DeleteNatGateway({ project_id, region, nat_gateway_id })`.
   - If the delete succeeds, skip cleanup and move to the final visibility check.
   - If the delete fails for any reason that does not clearly indicate an SNAT-rule dependency, stop and report the exact blocker without attempting cleanup.

6. If the delete is blocked by SNAT-rule dependencies, clean up only those SNAT rules.
   - Call `huaweicloud-nat_ListNatGatewaySnatRules({ project_id, region, nat_gateway_id: [nat_gateway_id] })`.
   - Enter this step only when the first delete error clearly points to a rule-dependency blocker.
   - Treat all SNAT rules currently returned for that same gateway as the only cleanup candidates.
   - Delete each returned SNAT rule with `huaweicloud-nat_DeleteNatGatewaySnatRule({ project_id, region, nat_gateway_id, snat_rule_id })`.
   - If SNAT cleanup finds zero rules or any SNAT deletion fails, stop and report the blocker instead of broadening cleanup.

7. Retry the gateway deletion once after SNAT cleanup.
   - Call `huaweicloud-nat_DeleteNatGateway({ project_id, region, nat_gateway_id })` one more time.
   - Do not loop or retry indefinitely.

8. Recheck visibility in the same scope.
   - Call `huaweicloud-nat_ListNatGateways({ project_id, region, id: nat_gateway_id })`.
   - If the result is empty, report that the gateway is no longer visible in this scope.
   - If the gateway still appears, report that deletion is blocked or incomplete.

## Interpretation rules

- An empty preflight list means the target gateway was not found in this region/project scope.
- A direct delete may fail with a dependency-style blocker such as undeleted rules; in this skill, automatic cleanup is allowed only when the delete error clearly indicates a rule-dependency blocker.
- When cleanup is allowed, only SNAT rules currently returned for that same gateway are eligible for deletion.
- A successful SNAT cleanup does not itself prove the NAT gateway is deleted; use the final read to confirm visibility.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.

## Safety and scope

- This skill is destructive.
- Delete only the explicitly identified gateway.
- Delete only SNAT rules returned for that same gateway in the current run.
- Do not delete DNAT rules, EIPs, tags, or any other dependent resources.
- Do not infer a different `project_id` or `region` silently.
- Do not broaden cleanup if the blocker is not clearly a same-gateway SNAT-rule dependency.
- Do not loop on retries; perform at most one cleanup pass and one gateway delete retry.

## Output checklist

1. region used
2. project used
3. preflight gateway match
4. first delete attempt result
5. exact blocker from the first delete failure, if any
6. whether SNAT cleanup was attempted and why
7. number of same-gateway SNAT rules found
8. exact SNAT rule IDs deleted, if any
9. retry delete result
10. exact blocker from the retry failure, if any
11. final NAT visibility check result
12. overall outcome: `completed`, `partially completed`, or `blocked`
13. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
