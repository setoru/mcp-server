---
name: huawei-nat-create-snat-rule
description: Create a Huawei Cloud public SNAT rule for outbound internet access through the repo-local NAT MCP server. Use when the user explicitly wants egress internet access for a subnet or CIDR behind an existing public NAT gateway.
compatibility: Prefers the repo's opencode.json to expose the local `huaweicloud-nat` MCP server. If that tool is unavailable but the repo-local NAT helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: nat
  purpose: create-snat-rule
---

# Huawei NAT Create SNAT Rule

## What this skill does

- Create exactly one public SNAT rule.
- Use SNAT as the outbound internet access rule for a public NAT gateway.
- Stop after the create call returns.

## Tool assumptions

This skill expects the project-local MCP server name to be `huaweicloud-nat`, so the primary tools are:

- `huaweicloud-nat_ListNatGateways`
- `huaweicloud-nat_CreateNatGatewaySnatRule`

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.

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
- `floating_ip_id`
- exactly one of `network_id` or `cidr`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `description`
- `source_type`
- `global_eip_id`

## Default workflow

1. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })`.

2. Treat this as the outbound internet access rule skill.
   - Use SNAT, not DNAT, for outbound internet access.

3. Require explicit identifiers.
   - If `project_id`, `nat_gateway_id`, or `floating_ip_id` is still missing, ask for the missing field.
   - Require exactly one of `network_id` or `cidr`.
   - Do not guess subnet scope, VPC scope, or EIP choice.

4. Run a minimal NAT gateway preflight:
   - `huaweicloud-nat_ListNatGateways({ project_id, region, id: nat_gateway_id })`
   - If no gateway is returned, stop and report that the target gateway was not found.
   - If the returned gateway status is present and is not `ACTIVE`, stop and report that blocker.

6. Create exactly one SNAT rule using the flattened MCP tool schema:
   - `huaweicloud-nat_CreateNatGatewaySnatRule({ project_id, region, nat_gateway_id, floating_ip_id, network_id? or cidr?, description?, source_type?, global_eip_id? })`

7. Stop after the create result.

## Safety and scope

- This skill performs one mutating action.
- It is for outbound internet access only.
- Do not create a NAT gateway automatically.
- Do not create DNAT rules here.
- Do not create more than one rule in a single use of this skill.

## Output checklist

1. region used
2. project used
3. target NAT gateway ID
4. scope selector used (`network_id` or `cidr`)
5. returned SNAT rule ID and status if present
6. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
