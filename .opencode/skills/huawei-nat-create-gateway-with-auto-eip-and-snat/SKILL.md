---
name: huawei-nat-create-gateway-with-auto-eip-and-snat
description: Create one Huawei Cloud public NAT gateway and one SNAT rule in a single flow by reusing an existing suitable EIP when possible, or creating a new EIP when needed. Use when the user explicitly wants outbound NAT set up without repeated confirmation prompts and the end goal is a successfully created NAT path, not an early blocker report.
compatibility: Prefers the repo's `opencode.json` to expose local `huaweicloud-nat` and `huaweicloud-eip` MCP servers. If those tools are unavailable but the repo-local NAT/EIP helper paths are present, this skill may use those bounded fallback paths instead.
metadata:
  domain: huaweicloud
  service: nat
  purpose: create-gateway-with-auto-eip-and-snat
---

# Huawei NAT Create Gateway With Auto EIP And SNAT

## What this skill does

- Create exactly one public NAT gateway.
- Reuse one existing suitable EIP when there is a single clear reusable candidate in the current scope.
- Otherwise create exactly one new EIP when direct EIP create capability is available.
- Create exactly one public SNAT rule after the NAT gateway is readable and `ACTIVE`.
- When the active runtime initially lacks exposed EIP MCP tools, use the smallest repo-local helper-path fallback needed to finish the same bounded workflow.
- Report the NAT, EIP, and SNAT results conservatively.

## Tool assumptions

This skill expects the project-local MCP server name to be `huaweicloud-nat`, so the primary NAT tools are:

- `huaweicloud-nat_CreateNatGateway`
- `huaweicloud-nat_ListNatGateways`
- `huaweicloud-nat_CreateNatGatewaySnatRule`
- `huaweicloud-nat_ListNatGatewaySnatRules`

This skill prefers direct EIP MCP operations to be available in the current environment for the equivalent of:

- `ListPublicips`
- `ShowPublicip`
- `CreatePublicip`

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
This skill may reuse or create an EIP, but it must not silently guess among multiple existing EIP candidates.

The preferred runtime shape in this repo is still that `opencode.json` exposes both:

- `huaweicloud-nat`
- `huaweicloud-eip`

If direct EIP MCP operations are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local EIP execution path is available, specifically:

- `huaweicloud_services_server/mcp_server_eip/src/mcp_server_eip/run.py`
- `huaweicloud_services_server/mcp_server_eip/src/mcp_server_eip/config/config.yaml`
- `huaweicloud_services_server/mcp_server_eip/src/mcp_server_eip/config/eip.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`

When those repo-local files exist, this skill may use the repo-local helper execution path that loads `config.yaml` plus `eip.json`/`nat.json` and performs the exact same EIP/NAT operations through the repository's own OpenAPI execution chain.

Only report a blocker when neither the active MCP tool surface nor the repo-local execution path can safely provide the required EIP list/read/create capability.

## Runtime fallback when required tools are unavailable

If the expected NAT or EIP MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local NAT/EIP execution paths are available, using:

- `huaweicloud_services_server/mcp_server_nat/src/mcp_server_nat/run.py`
- `huaweicloud_services_server/mcp_server_nat/src/mcp_server_nat/config/config.yaml`
- `huaweicloud_services_server/mcp_server_nat/src/mcp_server_nat/config/nat.json`
- `huaweicloud_services_server/mcp_server_eip/src/mcp_server_eip/run.py`
- `huaweicloud_services_server/mcp_server_eip/src/mcp_server_eip/config/config.yaml`
- `huaweicloud_services_server/mcp_server_eip/src/mcp_server_eip/config/eip.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When those repo-local specs are present and valid for the required operations, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local NAT/EIP execution paths can safely provide the required capabilities.

## Required inputs

- `project_id`
- `name`
- `router_id`
- `internal_network_id`
- `spec`
- exactly one of `network_id` or `cidr`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `description`
- `enterprise_project_id`
- `ngport_ip_address`
- `source_type`
- `global_eip_id`
- EIP create fields required by the current EIP execution path when a new EIP must be allocated, such as public IP type and bandwidth settings

## Default workflow

1. Confirm the user explicitly wants outbound NAT created.
   - This skill performs intentional create actions.
   - Use it only when the user has already explicitly asked to create one NAT gateway and its outbound SNAT path.
   - Once explicit user intent is established, do not add extra confirmation prompts inside this skill.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })` before creation.
   - If `name`, `router_id`, `internal_network_id`, or `spec` is still missing, ask for the missing field.
   - If `project_id`, `name`, `router_id`, `internal_network_id`, or `spec` is still missing, ask for the missing field.
   - Require exactly one of `network_id` or `cidr`.
   - Do not guess VPC IDs, subnet IDs, NAT spec values, or region/project scope.

3. Resolve the EIP strategy before creating SNAT.
   - Prefer direct EIP MCP list/create operations when they are available in the active runtime.
    - If they are not available yet, first try the smallest repo-local helper fallback that keeps the workflow bounded: use the repo-local execution path backed by `assets/utils/hwc_tools.py` and the EIP/NAT OpenAPI specs.
   - List existing EIPs in the same region/project scope.
   - Reuse an existing EIP only when current EIP list/read results show exactly one clear reusable candidate in this same region/project scope and no conflicting candidate remains.
   - If there are zero suitable reusable candidates, create exactly one new EIP.
   - If there are multiple plausible reusable EIP candidates, do not guess among them; create a new EIP instead only when the required EIP-create fields are explicitly present or defaulted, otherwise report the blocker.
   - If a new EIP must be created but the required EIP-create fields supported by the current execution path are incomplete, stop and report that blocker instead of guessing billable settings.
    - If the active MCP runtime still lacks those tools, the repo-local helper execution path is still allowed for this one bounded run.

4. Create the NAT gateway once.
   - Call `huaweicloud-nat_CreateNatGateway({ project_id, region, name, router_id, internal_network_id, spec, description?, enterprise_project_id?, ngport_ip_address?, session_conf? })`.
   - Treat a returned pending state such as `PENDING_CREATE` as request acceptance, not as proof that the gateway is ready for SNAT.
   - If the create response does not yield a usable `nat_gateway_id`, stop and report that blocker.

5. Read back the NAT gateway until it is usable for SNAT.
   - Call `huaweicloud-nat_ListNatGateways({ project_id, region, id: nat_gateway_id })` using the returned gateway ID.
   - Use a bounded wait strategy such as a small fixed number of follow-up reads or a short total timeout, then report the last observed NAT status.
   - Proceed only when the returned gateway is visible and its status is `ACTIVE`.
   - If the gateway remains missing or non-`ACTIVE`, stop and report that blocker instead of attempting SNAT.

6. Create exactly one SNAT rule using the resolved EIP.
   - If EIP reuse/create did not yield an exact `floating_ip_id`, stop and report that blocker before SNAT.
   - Call `huaweicloud-nat_CreateNatGatewaySnatRule({ project_id, region, nat_gateway_id, floating_ip_id, network_id? or cidr?, description?, source_type?, global_eip_id? })`.
   - Do not substitute a different EIP after this step begins unless the skill is still inside the bounded EIP resolution logic from step 3.

7. Re-read and report the final state.
   - Re-check the NAT gateway with `huaweicloud-nat_ListNatGateways({ project_id, region, id: nat_gateway_id })` or the equivalent repo-local helper execution path.
   - Re-check the created SNAT rule with `huaweicloud-nat_ListNatGatewaySnatRules({ project_id, region, id: snat_rule_id })` or the equivalent repo-local helper execution path when an SNAT rule ID is returned.
   - Re-check the chosen or created EIP with the available EIP read/list tool or equivalent repo-local helper execution path when practical.
   - Report NAT status, EIP identity, and SNAT status separately.

## Interpretation rules

- A successful NAT create response does not by itself prove the gateway is ready for SNAT; the follow-up read must confirm `ACTIVE`.
- A successful SNAT create response does not by itself prove the SNAT rule is fully usable; use the follow-up read to confirm returned visibility and status.
- Reusing an EIP is allowed only when there is a single clear reusable candidate from current EIP reads in the same region/project scope.
- When there is no clear reusable EIP candidate, creating a new EIP is safer than guessing among existing ones.
- Creating a new EIP is allowed only when the required EIP-create fields are explicitly available from the call or defaults supported by the current execution path.
- If active MCP EIP tools are missing but the repo-local EIP server and helper chain are present, that is a remediation path, not an immediate blocker.
- Declaring a blocker is correct only after both the active MCP tool surface and the repo-local execution path fail to provide safe EIP list/read/create capability.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.

## Safety and scope

- This skill performs up to three ordered actions: optional EIP creation, NAT creation, and SNAT creation, with repo-local helper fallback allowed when NAT or EIP tools are not exposed.
- Create only one NAT gateway, at most one EIP, and one SNAT rule in a single use of this skill.
- Do not create DNAT rules here.
- Do not guess among multiple existing EIPs.
- Do not proceed to SNAT when the new NAT gateway is not yet `ACTIVE`.
- Do not chain cleanup or delete operations.
- Do not perform broad runtime refactors; keep the fallback to the smallest helper-path execution needed for this one workflow.

## Output checklist

1. region used
2. project used
3. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
4. whether repo-local helper fallback was used
5. EIP resolution mode used: `reused`, `created`, or `blocked`
6. exact EIP ID chosen or created
7. exact reason a new EIP was created or why auto-EIP was blocked
8. NAT create payload fields actually sent
9. returned NAT gateway ID
10. confirmed NAT status before SNAT
11. SNAT create payload fields actually sent
12. returned SNAT rule ID
13. confirmed SNAT status after follow-up, if checked
14. whether EIP follow-up verification was skipped and why
15. whether SNAT follow-up verification was skipped and why
16. resources already created when the run ended partially completed
17. exact blocker if creation was incomplete
18. overall outcome: `completed`, `partially completed`, or `blocked`
